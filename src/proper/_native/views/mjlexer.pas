(* minijx: template lexer.

  Turns a .jx source into a flat token stream: text, `{{ expr }}`,
  `{% stmt %}`, `<Component ...>`, `</Component>`. Comments are dropped and
  `{% raw %}` blocks come out as text. The lexer decides where each construct
  ends but does not look inside expressions. *)
unit mjlexer;

{$mode objfpc}{$H+}

interface

uses
  SysUtils, StrUtils, mjerrors, mjutil;

type
  TTokKind = (tkText, tkExpr, tkStmt, tkTagOpen, tkTagClose, tkDecl, tkComment, tkRaw);
  TAttrKind = (akFlag, akString, akExpr);

  TAttr = record
    Name: string;      (* exactly as written *)
    Value: string;     (* string: source text with quotes; expr: the inside of {{ }} *)
    Kind: TAttrKind;
    Pos: Integer;      (* 1-based offset of the name *)
    ValuePos: Integer; (* 1-based offset of the value's first char (inside quotes/braces) *)
  end;
  TAttrArray = array of TAttr;

  TToken = record
    Kind: TTokKind;
    Value: string;     (* text; expression body; statement body after the keyword *)
    Name: string;      (* statement keyword or tag name *)
    Pos: Integer;      (* 1-based offset of the token *)
    ValuePos: Integer; (* 1-based offset of Value in the source *)
    Attrs: TAttrArray;
    SelfClosing: Boolean;
    (* Jinja whitespace control: `{%-`, `{{-`, `{#-` strip the text before
       the tag; `-%}`, `-}}`, `-#}` the text after it. For a raw block they
       are the outer markers, `{%- raw` and `endraw -%}`. *)
    LStrip: Boolean;
    RStrip: Boolean;
  end;
  TTokenArray = array of TToken;

function Lex(const FileName, Src: string): TTokenArray;

implementation

type
  TLexer = class
  private
    FFile: string;
    FSrc: string;
    FLen: Integer;
    FOut: TTokenArray;
    FCount: Integer;
    procedure Emit(const T: TToken);
    procedure EmitText(Start, Stop: Integer);
    procedure Fail(Offset: Integer; const Msg: string);
    function FindExprEnd(I: Integer): Integer;
    function ScanExpr(I: Integer): Integer;
    function ScanComment(I: Integer): Integer;
    function EmitDeclaration(I, Stop: Integer): Boolean;
    procedure EmitComment(I, Stop: Integer);
    function ScanStmt(I: Integer): Integer;
    function ScanTag(I: Integer): Integer;
    function ScanCloseTag(I: Integer): Integer;
    function MatchEndRaw(I: Integer; out Stop: Integer; out LStrip, RStrip: Boolean): Boolean;
    function IsTagStart(I: Integer): Boolean;
    function IsCloseTagStart(I: Integer): Boolean;
  public
    function Run(const AFile, ASrc: string): TTokenArray;
  end;

procedure TLexer.Fail(Offset: Integer; const Msg: string);
begin
  CompileError(FFile, FSrc, Offset, Msg);
end;

procedure TLexer.Emit(const T: TToken);
begin
  if FCount = Length(FOut) then
    SetLength(FOut, 16 + FCount * 2);
  FOut[FCount] := T;
  Inc(FCount);
end;

procedure TLexer.EmitText(Start, Stop: Integer);
var
  T: TToken;
begin
  if Stop <= Start then
    Exit;
  T := Default(TToken);
  T.Kind := tkText;
  T.Pos := Start;
  T.ValuePos := Start;
  T.Value := NormalizeNewlines(Copy(FSrc, Start, Stop - Start));
  Emit(T);
end;

(* I points at the first char after `{{`. Returns the offset of the closing
  `}}`, tracking quotes and brackets so `{{ {'a': 1} }}` works. *)
function TLexer.FindExprEnd(I: Integer): Integer;
var
  Stack: string; (* open brackets, innermost last *)
  Quote: Char;
  Start: Integer;
begin
  Start := I;
  Stack := '';
  Quote := #0;
  while I <= FLen do
  begin
    if Quote <> #0 then
    begin
      if FSrc[I] = '\' then
        Inc(I)
      else if FSrc[I] = Quote then
        Quote := #0;
    end
    else
      case FSrc[I] of
        '"', '''': Quote := FSrc[I];
        '(', '[', '{': Stack := Stack + FSrc[I];
        ')', ']':
          if Stack <> '' then
            SetLength(Stack, Length(Stack) - 1);
        '}':
          begin
            (* only a `{` is closed by `}`; with a `(` or `[` still open,
               `}}` ends the expression and the parser reports what is
               missing *)
            if (Stack <> '') and (Stack[Length(Stack)] = '{') then
              SetLength(Stack, Length(Stack) - 1)
            else if (I < FLen) and (FSrc[I + 1] = '}') then
              Exit(I);
          end;
      end;
    Inc(I);
  end;
  Fail(Start - 2, 'Unclosed `{{`');
  Result := 0;
end;

function TLexer.ScanExpr(I: Integer): Integer;
var
  T: TToken;
  Stop, S, E: Integer;
begin
  Stop := FindExprEnd(I + 2);
  S := I + 2;
  E := Stop;
  T := Default(TToken);
  T.LStrip := (S < E) and (FSrc[S] = '-');
  if (S < E) and (FSrc[S] in ['-', '+']) then
    Inc(S);
  T.RStrip := (E > S) and (FSrc[E - 1] = '-');
  if (E > S) and (FSrc[E - 1] in ['-', '+']) then
    Dec(E);
  T.Kind := tkExpr;
  T.Pos := I;
  T.ValuePos := S;
  T.Value := Copy(FSrc, S, E - S);
  Emit(T);
  Result := Stop + 2;
end;

function TLexer.ScanComment(I: Integer): Integer;
var
  P: Integer;
begin
  P := Pos('#}', FSrc, I + 2);
  if P = 0 then
    Fail(I, 'Unclosed `{#`');
  Result := P + 2;
end;

(* A `{# def|import|css|js payload #}` in the header becomes a tkDecl token,
   following Jx's `split_declaration`: optional `-` markers, the keyword must
   be followed by whitespace and a non-empty payload, and `# ...` inline
   comments outside quotes are dropped (blanked, so offsets still match the
   source). Anything else is an ordinary comment and emits nothing. *)
function TLexer.EmitDeclaration(I, Stop: Integer): Boolean;
var
  S, E, KStart: Integer;
  Keyword, Payload: string;
  Quote: Char;
  j: Integer;
  T: TToken;
begin
  Result := False;
  S := I + 2;
  E := Stop - 2;
  if (S < E) and (FSrc[S] = '-') then
    Inc(S);
  if (E > S) and (FSrc[E - 1] = '-') then
    Dec(E);
  while (S < E) and (FSrc[S] in WhitespaceChars) do
    Inc(S);
  KStart := S;
  while (S < E) and (FSrc[S] in ['a'..'z', '_']) do
    Inc(S);
  Keyword := Copy(FSrc, KStart, S - KStart);
  if not InList(Keyword, ['def', 'import', 'css', 'js']) then
    Exit;
  if (S >= E) or not (FSrc[S] in WhitespaceChars) then
    Exit;
  while (S < E) and (FSrc[S] in WhitespaceChars) do
    Inc(S);
  Payload := Copy(FSrc, S, E - S);
  Quote := #0;
  j := 1;
  while j <= Length(Payload) do
  begin
    if Quote <> #0 then
    begin
      if Payload[j] = Quote then
        Quote := #0;
    end
    else if Payload[j] in ['"', ''''] then
      Quote := Payload[j]
    else if Payload[j] = '#' then
      while (j <= Length(Payload)) and (Payload[j] <> #10) do
      begin
        Payload[j] := ' ';
        Inc(j);
      end;
    Inc(j);
  end;
  Payload := TrimRight(Payload);
  if Payload = '' then
    Exit;
  T := Default(TToken);
  T.Kind := tkDecl;
  T.Pos := I;
  T.Name := Keyword;
  T.Value := Payload;
  T.ValuePos := S;
  T.LStrip := FSrc[I + 2] = '-';
  T.RStrip := (Stop - 3 > I + 2) and (FSrc[Stop - 3] = '-');
  Emit(T);
  Result := True;
end;

(* An ordinary comment renders nothing, but it separates the text around it,
   and its `{#-` / `-#}` markers trim that text, as in Jinja. *)
procedure TLexer.EmitComment(I, Stop: Integer);
var
  T: TToken;
begin
  T := Default(TToken);
  T.Kind := tkComment;
  T.Pos := I;
  T.ValuePos := I;
  T.LStrip := FSrc[I + 2] = '-';
  T.RStrip := (Stop - 3 > I + 2) and (FSrc[Stop - 3] = '-');
  Emit(T);
end;

(* Matches `{% endraw %}` (with optional -/+ markers) at I. *)
function TLexer.MatchEndRaw(I: Integer; out Stop: Integer; out LStrip, RStrip: Boolean): Boolean;
var
  J: Integer;
begin
  Result := False;
  LStrip := False;
  RStrip := False;
  if (I + 1 > FLen) or (FSrc[I] <> '{') or (FSrc[I + 1] <> '%') then
    Exit;
  J := I + 2;
  LStrip := (J <= FLen) and (FSrc[J] = '-');
  if (J <= FLen) and (FSrc[J] in ['-', '+']) then
    Inc(J);
  while (J <= FLen) and (FSrc[J] in WhitespaceChars) do
    Inc(J);
  if Copy(FSrc, J, 6) <> 'endraw' then
    Exit;
  Inc(J, 6);
  while (J <= FLen) and (FSrc[J] in WhitespaceChars) do
    Inc(J);
  RStrip := (J <= FLen) and (FSrc[J] = '-');
  if (J <= FLen) and (FSrc[J] in ['-', '+']) then
    Inc(J);
  if (J + 1 > FLen) or (FSrc[J] <> '%') or (FSrc[J + 1] <> '}') then
    Exit;
  Stop := J + 2;
  Result := True;
end;

function TLexer.ScanStmt(I: Integer): Integer;
var
  T: TToken;
  J, S, E, KStart, Stop: Integer;
  Quote: Char;
  Keyword: string;
  OpenStrip, CloseStrip, EndL, EndR: Boolean;
begin
  (* find `%}` outside of quotes *)
  J := I + 2;
  Quote := #0;
  Stop := 0;
  while J <= FLen do
  begin
    if Quote <> #0 then
    begin
      if FSrc[J] = '\' then
        Inc(J)
      else if FSrc[J] = Quote then
        Quote := #0;
    end
    else if FSrc[J] in ['"', ''''] then
      Quote := FSrc[J]
    else if (FSrc[J] = '%') and (J < FLen) and (FSrc[J + 1] = '}') then
    begin
      Stop := J;
      Break;
    end;
    Inc(J);
  end;
  if Stop = 0 then
    Fail(I, 'Unclosed `{%`');

  S := I + 2;
  E := Stop;
  OpenStrip := (S < E) and (FSrc[S] = '-');
  if (S < E) and (FSrc[S] in ['-', '+']) then
    Inc(S);
  CloseStrip := (E > S) and (FSrc[E - 1] = '-');
  if (E > S) and (FSrc[E - 1] in ['-', '+']) then
    Dec(E);
  while (S < E) and (FSrc[S] in WhitespaceChars) do
    Inc(S);
  KStart := S;
  while (S < E) and (FSrc[S] in NameChars) do
    Inc(S);
  Keyword := Copy(FSrc, KStart, S - KStart);
  if Keyword = '' then
    Fail(I, 'Empty statement');

  if Keyword = 'raw' then
  begin
    (* everything up to {% endraw %} is text; `raw -%}` and `{%- endraw`
       trim that text, `{%- raw` and `endraw -%}` the text around it *)
    J := Stop + 2;
    S := J;
    while J <= FLen do
    begin
      if (FSrc[J] = '{') and MatchEndRaw(J, E, EndL, EndR) then
      begin
        T := Default(TToken);
        T.Kind := tkRaw;
        T.Pos := I;
        T.ValuePos := S;
        T.Value := NormalizeNewlines(Copy(FSrc, S, J - S));
        if CloseStrip then
          T.Value := TrimLeftWS(T.Value);
        if EndL then
          T.Value := TrimRightWS(T.Value);
        T.LStrip := OpenStrip;
        T.RStrip := EndR;
        Emit(T);
        Exit(E);
      end;
      Inc(J);
    end;
    Fail(I, 'Unclosed `{% raw %}`');
  end;

  T := Default(TToken);
  T.Kind := tkStmt;
  T.LStrip := OpenStrip;
  T.RStrip := CloseStrip;
  T.Pos := I;
  T.Name := Keyword;
  while (S < E) and (FSrc[S] in WhitespaceChars) do
    Inc(S);
  T.ValuePos := S;
  T.Value := TrimRight(Copy(FSrc, S, E - S));
  Emit(T);
  Result := Stop + 2;
end;

function TLexer.IsTagStart(I: Integer): Boolean;
var
  J: Integer;
begin
  Result := False;
  if (I + 1 > FLen) or not (FSrc[I + 1] in TagNameStartChars) then
    Exit;
  J := I + 2;
  while (J <= FLen) and (FSrc[J] in TagNameChars) do
    Inc(J);
  Result := (J <= FLen) and (FSrc[J] in TagNameEndChars);
end;

function TLexer.IsCloseTagStart(I: Integer): Boolean;
begin
  Result := (I + 2 <= FLen) and (FSrc[I + 1] = '/') and (FSrc[I + 2] in TagNameStartChars);
end;

function TLexer.ScanTag(I: Integer): Integer;
var
  T: TToken;
  A: TAttr;
  J, NStart, N, K: Integer;
  Key: string;
  Quote: Char;
begin
  T := Default(TToken);
  T.Kind := tkTagOpen;
  T.Pos := I;
  J := I + 1;
  NStart := J;
  while (J <= FLen) and (FSrc[J] in TagNameChars) do
    Inc(J);
  T.Name := Copy(FSrc, NStart, J - NStart);
  N := 0;
  while True do
  begin
    while (J <= FLen) and (FSrc[J] in WhitespaceChars) do
      Inc(J);
    if J > FLen then
      Fail(I, 'Unclosed `<' + T.Name + '`');
    if (FSrc[J] = '/') and (J < FLen) and (FSrc[J + 1] = '>') then
    begin
      T.SelfClosing := True;
      Inc(J, 2);
      Break;
    end;
    if FSrc[J] = '>' then
    begin
      Inc(J);
      Break;
    end;
    if (FSrc[J] = '{') and (J < FLen) and (FSrc[J + 1] = '#') then
    begin
      J := ScanComment(J);
      Continue;
    end;
    if not (FSrc[J] in AttrNameStartChars) then
      Fail(J, 'Unexpected `' + FSrc[J] + '` in `<' + T.Name + '>`');
    A := Default(TAttr);
    A.Pos := J;
    NStart := J;
    while (J <= FLen) and (FSrc[J] in AttrNameChars) do
      Inc(J);
    A.Name := Copy(FSrc, NStart, J - NStart);
    (* optional `= value` *)
    NStart := J;
    while (J <= FLen) and (FSrc[J] in WhitespaceChars) do
      Inc(J);
    if (J <= FLen) and (FSrc[J] = '=') then
    begin
      Inc(J);
      while (J <= FLen) and (FSrc[J] in WhitespaceChars) do
        Inc(J);
      if J > FLen then
        Fail(A.Pos, 'Attribute `' + A.Name + '` has no value');
      if FSrc[J] in ['"', ''''] then
      begin
        Quote := FSrc[J];
        NStart := J;
        Inc(J);
        while (J <= FLen) and (FSrc[J] <> Quote) do
        begin
          if FSrc[J] = '\' then
            Inc(J);
          Inc(J);
        end;
        if J > FLen then
          Fail(NStart, 'Unclosed string in attribute `' + A.Name + '`');
        Inc(J);
        A.Kind := akString;
        A.ValuePos := NStart;
        A.Value := Copy(FSrc, NStart, J - NStart);
      end
      else if (FSrc[J] = '{') and (J < FLen) and (FSrc[J + 1] = '{') then
      begin
        NStart := FindExprEnd(J + 2);
        A.Kind := akExpr;
        A.ValuePos := J + 2;
        A.Value := Copy(FSrc, J + 2, NStart - J - 2);
        J := NStart + 2;
      end
      else
        Fail(J, 'Attribute `' + A.Name + '` value must be a quoted string or {{ expr }}');
    end
    else
    begin
      J := NStart;
      A.Kind := akFlag;
    end;
    (* as Jx: `data-id` and `data_id` are the same argument *)
    Key := ReplaceChar(A.Name, '-', '_');
    for K := 0 to N - 1 do
      if ReplaceChar(T.Attrs[K].Name, '-', '_') = Key then
        Fail(A.Pos, 'Duplicate attribute `' + A.Name + '` on `' + T.Name + '`');
    SetLength(T.Attrs, N + 1);
    T.Attrs[N] := A;
    Inc(N);
  end;
  Emit(T);
  Result := J;
end;

function TLexer.ScanCloseTag(I: Integer): Integer;
var
  T: TToken;
  J, NStart: Integer;
begin
  T := Default(TToken);
  T.Kind := tkTagClose;
  T.Pos := I;
  J := I + 2;
  NStart := J;
  while (J <= FLen) and (FSrc[J] in TagNameChars) do
    Inc(J);
  T.Name := Copy(FSrc, NStart, J - NStart);
  while (J <= FLen) and (FSrc[J] in WhitespaceChars) do
    Inc(J);
  if (J > FLen) or (FSrc[J] <> '>') then
    Fail(I, 'Malformed `</' + T.Name + '>`');
  Emit(T);
  Result := J + 1;
end;

function TLexer.Run(const AFile, ASrc: string): TTokenArray;
var
  I, TextStart, Brace, Angle, Nxt, Stop: Integer;
  C: Char;
  InHeader: Boolean;
begin
  InHeader := True;
  FFile := AFile;
  FSrc := ASrc;
  FLen := Length(ASrc);
  FCount := 0;
  SetLength(FOut, 0);
  I := 1;
  TextStart := 1;
  Brace := Pos('{', FSrc);
  Angle := Pos('<', FSrc);
  while I <= FLen do
  begin
    if (Brace <> 0) and (Brace < I) then
      Brace := PosEx('{', FSrc, I);
    if (Angle <> 0) and (Angle < I) then
      Angle := PosEx('<', FSrc, I);
    if Brace = 0 then
      Nxt := Angle
    else if Angle = 0 then
      Nxt := Brace
    else if Brace < Angle then
      Nxt := Brace
    else
      Nxt := Angle;
    if Nxt = 0 then
      Break;
    I := Nxt;
    C := FSrc[I];
    if (C = '{') and (I < FLen) then
    begin
      case FSrc[I + 1] of
        '{':
          begin
            InHeader := False;
            EmitText(TextStart, I);
            I := ScanExpr(I);
            TextStart := I;
            Continue;
          end;
        '%':
          begin
            InHeader := False;
            EmitText(TextStart, I);
            I := ScanStmt(I);
            TextStart := I;
            Continue;
          end;
        '#':
          begin
            (* the header is the run of comments the file starts with,
               with nothing but whitespace between them, as in Jx *)
            if InHeader and not IsBlank(Copy(FSrc, TextStart, I - TextStart)) then
              InHeader := False;
            EmitText(TextStart, I);
            Stop := ScanComment(I);
            if not (InHeader and EmitDeclaration(I, Stop)) then
              EmitComment(I, Stop);
            I := Stop;
            TextStart := I;
            Continue;
          end;
      end;
    end
    else if C = '<' then
    begin
      if IsTagStart(I) then
      begin
        InHeader := False;
        EmitText(TextStart, I);
        I := ScanTag(I);
        TextStart := I;
        Continue;
      end
      else if IsCloseTagStart(I) then
      begin
        InHeader := False;
        EmitText(TextStart, I);
        I := ScanCloseTag(I);
        TextStart := I;
        Continue;
      end;
    end;
    Inc(I);
  end;
  EmitText(TextStart, FLen + 1);
  (* Jinja's keep_trailing_newline=False: one newline at the very end of the
     template is dropped *)
  if (FCount > 0) and (FOut[FCount - 1].Kind = tkText) and
    EndsWith(FOut[FCount - 1].Value, #10) then
    SetLength(FOut[FCount - 1].Value, Length(FOut[FCount - 1].Value) - 1);
  SetLength(FOut, FCount);
  Result := FOut;
end;

function Lex(const FileName, Src: string): TTokenArray;
var
  L: TLexer;
begin
  L := TLexer.Create;
  try
    Result := L.Run(FileName, Src);
  finally
    L.Free;
  end;
end;

end.
