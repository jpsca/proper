(* minijx: template parser.

  Builds a tree from the lexer's tokens and collects the header declarations
  (`{# def #}`, `{# import #}`, `{# css #}`, `{# js #}`). Expressions are
  kept as source text; the code generator translates them with the scope
  they appear in. *)
unit mjparser;

{$mode objfpc}{$H+}

interface

uses
  SysUtils, Classes, StrUtils, mjerrors, mjutil, mjlexer;

type
  TNodeKind = (nkText, nkOutput, nkIf, nkFor, nkSet, nkDo, nkFilter, nkSlot,
    nkFill, nkComponent,
    nkTag,     (* {% name args %}body{% endname %} -> tags[name](args, caller=body) *)
    nkMacro,   (* {% macro name(params) %}body{% endmacro %} -> a nested function *)
    nkComment, (* renders nothing, but separates the text around it *)
    nkRaw);    (* text from {% raw %}; never trimmed by its neighbours *)

  TNode = class;
  TNodeList = class;

  TBranch = record
    Cond: string;    (* '' for else *)
    CondPos: Integer;
    Body: TNodeList;
  end;

  TNode = class
  public
    Kind: TNodeKind;
    Pos: Integer;
    Text: string;          (* nkText *)
    Expr: string;          (* nkOutput, nkSet value, nkDo, nkFor header, nkFilter chain *)
    ExprPos: Integer;
    Name: string;          (* nkSlot/nkFill name, nkComponent alias, nkTag name *)
    Parens: Boolean;       (* nkTag: the arguments are written `name(...)` *)
    Body: TNodeList;       (* nkFor body, nkFilter, nkSlot default, nkFill, nkComponent children *)
    ElseBody: TNodeList;   (* nkFor *)
    Branches: array of TBranch; (* nkIf *)
    Attrs: TAttrArray;     (* nkComponent *)
    Fills: TNodeList;      (* nkComponent *)
    (* `{%-` before the node / `-%}` after it: trim the text next to it *)
    StripBefore: Boolean;
    StripAfter: Boolean;
    constructor Create(AKind: TNodeKind; APos: Integer);
    destructor Destroy; override;
  end;

  TNodeList = class
  private
    FItems: array of TNode;
    FCount: Integer;
    function GetItem(I: Integer): TNode;
  public
    destructor Destroy; override;
    procedure Add(N: TNode);
    property Count: Integer read FCount;
    property Items[I: Integer]: TNode read GetItem; default;
    (* Anything left once whitespace control has run: Jx passes content to a
       component whenever its tag has any, even if it renders to spaces. *)
    function HasContent: Boolean;
  public
    (* `-%}` of the tag that opens the list / `{%-` of the one that closes it *)
    StripStart: Boolean;
    StripEnd: Boolean;
  end;

  TImportDecl = record
    Path: string;
    Alias: string;
    Pos: Integer;
  end;

  TDocument = class
  public
    FileName: string;
    Source: string;
    DefExpr: string;   (* raw contents of {# def ... #} *)
    DefPos: Integer;
    HasDef: Boolean;
    Imports: array of TImportDecl;
    Css: TStringArray;
    Js: TStringArray;
    Body: TNodeList;
    constructor Create;
    destructor Destroy; override;
    function FindImport(const Alias: string): Integer;
  end;

(* Tags: the names of the custom tags (`{% cache ... %}...{% endcache %}`),
   or nil. *)
function ParseDocument(const FileName, Src: string; Tags: TStrings = nil): TDocument;

(* Why a name cannot be a custom tag, or '' if it can. *)
function TagNameError(const Name: string): string;

implementation

const
  (* the statements of Jinja and minijx, which a custom tag cannot shadow *)
  ReservedTags: array[0..31] of string = ('if', 'elif', 'else', 'for', 'set',
    'do', 'filter', 'call', 'slot', 'fill', 'raw', 'def', 'import', 'css', 'js',
    'extends', 'include', 'macro', 'block', 'with', 'autoescape', 'from', 'trans',
    'pluralize', 'break', 'continue', 'print', 'debug', 'namespace', 'caller',
    'true', 'false');

function TagNameError(const Name: string): string;
var
  i: Integer;
begin
  Result := '';
  if (Name = '') or not (Name[1] in ['a'..'z', 'A'..'Z', '_']) then
    Exit('not a valid name');
  for i := 1 to Length(Name) do
    if not (Name[i] in NameChars) then
      Exit('not a valid name');
  if InList(Name, ReservedTags) then
    Exit('a builtin statement');
  if StartsWith(Name, 'end') then
    Exit('it starts with `end`, which closes a block');
end;

(* TNode *)

constructor TNode.Create(AKind: TNodeKind; APos: Integer);
begin
  Kind := AKind;
  Pos := APos;
end;

destructor TNode.Destroy;
var
  i: Integer;
begin
  Body.Free;
  ElseBody.Free;
  Fills.Free;
  for i := 0 to High(Branches) do
    Branches[i].Body.Free;
  inherited;
end;

(* TNodeList *)

destructor TNodeList.Destroy;
var
  i: Integer;
begin
  for i := 0 to FCount - 1 do
    FItems[i].Free;
  inherited;
end;

procedure TNodeList.Add(N: TNode);
begin
  if FCount = Length(FItems) then
    SetLength(FItems, 8 + FCount * 2);
  FItems[FCount] := N;
  Inc(FCount);
end;

function TNodeList.GetItem(I: Integer): TNode;
begin
  Result := FItems[I];
end;

function TNodeList.HasContent: Boolean;
var
  i: Integer;
begin
  for i := 0 to FCount - 1 do
    if (FItems[i].Kind <> nkText) or (FItems[i].Text <> '') then
      Exit(True);
  Result := False;
end;

(* TDocument *)

constructor TDocument.Create;
begin
  Body := TNodeList.Create;
end;

destructor TDocument.Destroy;
begin
  Body.Free;
  inherited;
end;

function TDocument.FindImport(const Alias: string): Integer;
var
  i: Integer;
begin
  for i := 0 to High(Imports) do
    if Imports[i].Alias = Alias then
      Exit(i);
  Result := -1;
end;

(* Parser *)

type
  TParser = class
  private
    FDoc: TDocument;
    FToks: TTokenArray;
    FI: Integer;
    FTags: TStrings; (* custom tag names, or nil *)
    function IsTag(const Name: string): Boolean;
    procedure Fail(Offset: Integer; const Msg: string);
    procedure ParseHeader(const T: TToken);
    function ParseNodes(const StopKeywords: array of string; const StopTag: string;
      InComponent: TNode; OpenPos: Integer = 0): TNodeList;
    function ParseIf(const T: TToken): TNode;
    function ParseFor(const T: TToken): TNode;
    function ParseComponent(const T: TToken): TNode;
    function ParseStmtName(const T: TToken): string;
    procedure CloseBlock(N: TNode; const Open: TToken);
  public
    function Run(const FileName, Src: string): TDocument;
  end;

procedure TParser.Fail(Offset: Integer; const Msg: string);
begin
  CompileError(FDoc.FileName, FDoc.Source, Offset, Msg);
end;

function ParseFiles(const Expr: string): TStringArray;
var
  Parts: TStringArray;
  i, N: Integer;
  S: string;
begin
  Parts := Split(Expr, ',');
  SetLength(Result, 0);
  N := 0;
  for i := 0 to High(Parts) do
  begin
    S := Trim(Parts[i]);
    while (S <> '') and (S[1] in ['"', '''']) do
      Delete(S, 1, 1);
    while (S <> '') and (S[Length(S)] in ['"', '''', '/']) do
      Delete(S, Length(S), 1);
    if S <> '' then
    begin
      SetLength(Result, N + 1);
      Result[N] := S;
      Inc(N);
    end;
  end;
end;

procedure TParser.ParseHeader(const T: TToken);
var
  D: TImportDecl;
  S: string;
  Close, J, N: Integer;
  Files: TStringArray;
begin
  if T.Name = 'def' then
  begin
    if FDoc.HasDef then
      Fail(T.Pos, 'Duplicate `{# def #}`');
    FDoc.HasDef := True;
    FDoc.DefExpr := T.Value;
    FDoc.DefPos := T.ValuePos;
    Exit;
  end;
  if T.Name = 'import' then
  begin
    S := T.Value;
    if (S = '') or not (S[1] in ['"', '''']) then
      Fail(T.ValuePos, 'Expected `{# import "path.jx" as Name #}`');
    Close := PosEx(S[1], S, 2);
    if Close < 3 then
      Fail(T.ValuePos, 'Expected `{# import "path.jx" as Name #}`');
    D.Path := Copy(S, 2, Close - 2);
    D.Pos := T.Pos;
    J := Close + 1;
    while (J <= Length(S)) and (S[J] in WhitespaceChars) do
      Inc(J);
    if Copy(S, J, 2) <> 'as' then
      Fail(T.ValuePos + J - 1, 'Expected `as` after the import path');
    Inc(J, 2);
    if (J > Length(S)) or not (S[J] in WhitespaceChars) then
      Fail(T.ValuePos + J - 1, 'Expected a name after `as`');
    while (J <= Length(S)) and (S[J] in WhitespaceChars) do
      Inc(J);
    if (J > Length(S)) or not (S[J] in TagNameStartChars) then
      Fail(T.ValuePos + J - 1, 'Import alias must start with an uppercase letter');
    N := J;
    while (J <= Length(S)) and (S[J] in TagNameChars) do
      Inc(J);
    D.Alias := Copy(S, N, J - N);
    if J <= Length(S) then
      Fail(T.ValuePos + J - 1, 'Unexpected text after the import alias');
    if FDoc.FindImport(D.Alias) >= 0 then
      Fail(T.Pos, 'Duplicate import alias `' + D.Alias + '`');
    SetLength(FDoc.Imports, Length(FDoc.Imports) + 1);
    FDoc.Imports[High(FDoc.Imports)] := D;
    Exit;
  end;
  Files := ParseFiles(T.Value);
  if T.Name = 'css' then
  begin
    N := Length(FDoc.Css);
    SetLength(FDoc.Css, N + Length(Files));
    for J := 0 to High(Files) do
      FDoc.Css[N + J] := Files[J];
  end
  else
  begin
    N := Length(FDoc.Js);
    SetLength(FDoc.Js, N + Length(Files));
    for J := 0 to High(Files) do
      FDoc.Js[N + J] := Files[J];
  end;
end;

function TParser.ParseStmtName(const T: TToken): string;
var
  i: Integer;
begin
  Result := Trim(T.Value);
  if Result = '' then
    Fail(T.Pos, '`{% ' + T.Name + ' %}` needs a name');
  for i := 1 to Length(Result) do
    if not (Result[i] in NameChars) then
      Fail(T.ValuePos + i - 1, 'Invalid name `' + Result + '` in `{% ' + T.Name + ' %}`');
end;

(* Consumes the end tag of a single-body block (filter, slot, fill) and
   records the whitespace markers of both tags. *)
procedure TParser.CloseBlock(N: TNode; const Open: TToken);
var
  Close: TToken;
begin
  Close := FToks[FI];
  Inc(FI);
  N.StripBefore := Open.LStrip;
  N.Body.StripStart := Open.RStrip;
  N.Body.StripEnd := Close.LStrip;
  N.StripAfter := Close.RStrip;
end;

(* Jinja-style whitespace control, applied once the tree is built.

   A run of consecutive text nodes is one piece of template data for Jinja:
   nodes only end up next to each other when a fill between them was moved
   out (comments and raw blocks are nodes of their own). A marker trims the
   whole run next to it, up to the first non-whitespace character. *)
procedure StripLeading(L: TNodeList; From: Integer);
var
  j: Integer;
begin
  j := From;
  while (j < L.Count) and (L[j].Kind = nkText) do
  begin
    L[j].Text := TrimLeftWS(L[j].Text);
    if L[j].Text <> '' then
      Exit;
    Inc(j);
  end;
end;

procedure StripTrailing(L: TNodeList; From: Integer);
var
  j: Integer;
begin
  j := From;
  while (j >= 0) and (L[j].Kind = nkText) do
  begin
    L[j].Text := TrimRightWS(L[j].Text);
    if L[j].Text <> '' then
      Exit;
    Dec(j);
  end;
end;

procedure ApplyWhitespace(L: TNodeList);
var
  i, b: Integer;
  N: TNode;
begin
  if L = nil then
    Exit;
  if L.StripStart then
    StripLeading(L, 0);
  if L.StripEnd then
    StripTrailing(L, L.Count - 1);
  for i := 0 to L.Count - 1 do
  begin
    N := L[i];
    if N.StripBefore then
      StripTrailing(L, i - 1);
    if N.StripAfter then
      StripLeading(L, i + 1);
    ApplyWhitespace(N.Body);
    ApplyWhitespace(N.ElseBody);
    for b := 0 to High(N.Branches) do
      ApplyWhitespace(N.Branches[b].Body);
    if N.Fills <> nil then
      for b := 0 to N.Fills.Count - 1 do
        ApplyWhitespace(N.Fills[b].Body);
  end;
end;

function TParser.ParseIf(const T: TToken): TNode;
var
  B: TBranch;
  Tok: TToken;
begin
  Result := TNode.Create(nkIf, T.Pos);
  Result.StripBefore := T.LStrip;
  if Trim(T.Value) = '' then
    Fail(T.Pos, '`{% if %}` needs a condition');
  B.Cond := T.Value;
  B.CondPos := T.ValuePos;
  B.Body := ParseNodes(['elif', 'else', 'endif'], '', nil, T.Pos);
  B.Body.StripStart := T.RStrip;
  SetLength(Result.Branches, 1);
  Result.Branches[0] := B;
  while True do
  begin
    Tok := FToks[FI];
    Inc(FI);
    Result.Branches[High(Result.Branches)].Body.StripEnd := Tok.LStrip;
    if Tok.Name = 'endif' then
    begin
      Result.StripAfter := Tok.RStrip;
      Break;
    end;
    if Tok.Name = 'elif' then
    begin
      if Trim(Tok.Value) = '' then
        Fail(Tok.Pos, '`{% elif %}` needs a condition');
      B.Cond := Tok.Value;
      B.CondPos := Tok.ValuePos;
      B.Body := ParseNodes(['elif', 'else', 'endif'], '', nil, Tok.Pos);
    end
    else
    begin
      B.Cond := '';
      B.CondPos := Tok.ValuePos;
      B.Body := ParseNodes(['endif'], '', nil, Tok.Pos);
    end;
    B.Body.StripStart := Tok.RStrip;
    SetLength(Result.Branches, Length(Result.Branches) + 1);
    Result.Branches[High(Result.Branches)] := B;
  end;
end;

function TParser.ParseFor(const T: TToken): TNode;
var
  Tok: TToken;
begin
  Result := TNode.Create(nkFor, T.Pos);
  Result.StripBefore := T.LStrip;
  Result.Expr := T.Value;
  Result.ExprPos := T.ValuePos;
  Result.Body := ParseNodes(['else', 'endfor'], '', nil, T.Pos);
  Result.Body.StripStart := T.RStrip;
  Tok := FToks[FI];
  Inc(FI);
  Result.Body.StripEnd := Tok.LStrip;
  if Tok.Name = 'else' then
  begin
    Result.ElseBody := ParseNodes(['endfor'], '', nil, Tok.Pos);
    Result.ElseBody.StripStart := Tok.RStrip;
    Tok := FToks[FI];
    Inc(FI);
    Result.ElseBody.StripEnd := Tok.LStrip;
  end;
  Result.StripAfter := Tok.RStrip;
end;

function TParser.ParseComponent(const T: TToken): TNode;
begin
  Result := TNode.Create(nkComponent, T.Pos);
  Result.Name := T.Name;
  Result.Attrs := T.Attrs;
  Result.Fills := TNodeList.Create;
  if T.SelfClosing then
    Result.Body := TNodeList.Create
  else
  begin
    Result.Body := ParseNodes([], T.Name, Result);
    Inc(FI); (* the closing tag *)
  end;
  (* Jx turns the content into `{% call ... -%}content{%- endcall %}` (and
     strips it when there are fills), so it never keeps whitespace at its
     ends. *)
  Result.Body.StripStart := True;
  Result.Body.StripEnd := True;
end;

(* Parses until a statement whose keyword is in StopKeywords, or a closing tag
  named StopTag. The stopping token is left at FI. Fails at end of input if a
  stop was expected. *)
function TParser.ParseNodes(const StopKeywords: array of string; const StopTag: string;
  InComponent: TNode; OpenPos: Integer): TNodeList;
var
  T: TToken;
  N: TNode;
  i: Integer;
begin
  Result := TNodeList.Create;
  while FI < Length(FToks) do
  begin
    T := FToks[FI];
    case T.Kind of
      tkText:
        begin
          N := TNode.Create(nkText, T.Pos);
          N.Text := T.Value;
          Result.Add(N);
          Inc(FI);
        end;
      tkExpr:
        begin
          if Trim(T.Value) = '' then
            Fail(T.Pos, 'Empty `{{ }}`');
          N := TNode.Create(nkOutput, T.Pos);
          N.Expr := T.Value;
          N.ExprPos := T.ValuePos;
          N.StripBefore := T.LStrip;
          N.StripAfter := T.RStrip;
          Result.Add(N);
          Inc(FI);
        end;
      tkComment:
        begin
          N := TNode.Create(nkComment, T.Pos);
          N.StripBefore := T.LStrip;
          N.StripAfter := T.RStrip;
          Result.Add(N);
          Inc(FI);
        end;
      tkRaw:
        begin
          N := TNode.Create(nkRaw, T.Pos);
          N.Text := T.Value;
          N.StripBefore := T.LStrip;
          N.StripAfter := T.RStrip;
          Result.Add(N);
          Inc(FI);
        end;
      tkTagClose:
        begin
          if T.Name = StopTag then
            Exit;
          Fail(T.Pos, 'Unexpected `</' + T.Name + '>`');
        end;
      tkTagOpen:
        begin
          Inc(FI);
          Result.Add(ParseComponent(T));
        end;
      tkDecl:
        begin
          Inc(FI);
          ParseHeader(T);
          (* still a comment for Jinja: it separates and can trim text *)
          N := TNode.Create(nkComment, T.Pos);
          N.StripBefore := T.LStrip;
          N.StripAfter := T.RStrip;
          Result.Add(N);
        end;
      tkStmt:
        begin
          if InList(T.Name, StopKeywords) then
            Exit;
          Inc(FI);
          case T.Name of
            'def', 'import', 'css', 'js':
              Fail(T.Pos, 'Declarations are comments, as in Jx: write `{# ' + T.Name +
                ' ... #}` at the top of the file');
            'if':
              Result.Add(ParseIf(T));
            'for':
              Result.Add(ParseFor(T));
            'set':
              begin
                if Pos('=', T.Value) = 0 then
                  Fail(T.Pos, 'minijx only supports `{% set name = value %}`');
                N := TNode.Create(nkSet, T.Pos);
                N.Expr := T.Value;
                N.ExprPos := T.ValuePos;
                N.StripBefore := T.LStrip;
                N.StripAfter := T.RStrip;
                Result.Add(N);
              end;
            'do':
              begin
                if Trim(T.Value) = '' then
                  Fail(T.Pos, '`{% do %}` needs an expression');
                N := TNode.Create(nkDo, T.Pos);
                N.Expr := T.Value;
                N.ExprPos := T.ValuePos;
                N.StripBefore := T.LStrip;
                N.StripAfter := T.RStrip;
                Result.Add(N);
              end;
            'filter':
              begin
                if Trim(T.Value) = '' then
                  Fail(T.Pos, '`{% filter %}` needs a filter name');
                N := TNode.Create(nkFilter, T.Pos);
                N.Expr := T.Value;
                N.ExprPos := T.ValuePos;
                N.Body := ParseNodes(['endfilter'], '', nil, T.Pos);
                CloseBlock(N, T);
                Result.Add(N);
              end;
            'macro':
              begin
                if Trim(T.Value) = '' then
                  Fail(T.Pos, '`{% macro %}` needs a name and parameters: `{% macro name(a, b=1) %}`');
                N := TNode.Create(nkMacro, T.Pos);
                (* the name, for the generator to bind it before the code
                   that comes first; the translator checks it *)
                N.Name := Trim(T.Value);
                i := 1;
                while (i <= Length(N.Name)) and (N.Name[i] in NameChars) do
                  Inc(i);
                N.Name := Copy(N.Name, 1, i - 1);
                N.Expr := T.Value;
                N.ExprPos := T.ValuePos;
                N.Body := ParseNodes(['endmacro'], '', nil, T.Pos);
                CloseBlock(N, T);
                Result.Add(N);
              end;
            'slot':
              begin
                N := TNode.Create(nkSlot, T.Pos);
                N.Name := ParseStmtName(T);
                N.Body := ParseNodes(['endslot'], '', nil, T.Pos);
                CloseBlock(N, T);
                Result.Add(N);
              end;
            'fill':
              begin
                if InComponent = nil then
                  Fail(T.Pos, '`{% fill %}` is only allowed directly inside a component tag');
                N := TNode.Create(nkFill, T.Pos);
                N.Name := ParseStmtName(T);
                N.Body := ParseNodes(['endfill'], '', nil, T.Pos);
                CloseBlock(N, T);
                (* Jx moves the fill out of the content, so the markers
                   outside of it (`{%- fill`, `endfill -%}`) do nothing *)
                N.StripBefore := False;
                N.StripAfter := False;
                InComponent.Fills.Add(N);
              end;
            'elif', 'else', 'endif', 'endfor', 'endfilter', 'endslot', 'endfill', 'endmacro':
              Fail(T.Pos, 'Unexpected `{% ' + T.Name + ' %}`');
            'extends', 'include', 'call', 'endcall', 'block', 'with', 'autoescape', 'endraw', 'endset', 'endblock', 'endwith', 'endautoescape':
              Fail(T.Pos, '`{% ' + T.Name + ' %}` is not supported by minijx');
          else
            if IsTag(T.Name) then
            begin
              N := TNode.Create(nkTag, T.Pos);
              N.Name := T.Name;
              N.Expr := T.Value;
              N.ExprPos := T.ValuePos;
              (* `{% cache(a, b) %}` is a call; `{% cache (a, b) %}`, with a
                 space, one argument, a tuple, as in Jinja *)
              N.Parens := (T.Value <> '') and (T.Value[1] = '(') and
                (FDoc.Source[T.ValuePos - 1] in NameChars);
              N.Body := ParseNodes(['end' + T.Name], '', nil, T.Pos);
              CloseBlock(N, T);
              Result.Add(N);
            end
            else if StartsWith(T.Name, 'end') and IsTag(Copy(T.Name, 4, MaxInt)) then
              Fail(T.Pos, 'Unexpected `{% ' + T.Name + ' %}`')
            else
              Fail(T.Pos, 'Unknown statement `{% ' + T.Name + ' %}`');
          end;
        end;
    end;
  end;
  if StopTag <> '' then
    Fail(InComponent.Pos, 'Unclosed `<' + StopTag + '>`');
  if Length(StopKeywords) > 0 then
    Fail(OpenPos, 'Unclosed block: expected `{% ' + StopKeywords[High(StopKeywords)] + ' %}` before the end of the file');
end;

function TParser.IsTag(const Name: string): Boolean;
begin
  Result := (FTags <> nil) and (FTags.IndexOf(Name) >= 0);
end;

function TParser.Run(const FileName, Src: string): TDocument;
begin
  FDoc := TDocument.Create;
  FDoc.FileName := FileName;
  FDoc.Source := Src;
  FToks := Lex(FileName, Src);
  FI := 0;
  FDoc.Body.Free;
  FDoc.Body := ParseNodes([], '', nil);
  ApplyWhitespace(FDoc.Body);
  Result := FDoc;
end;

function ParseDocument(const FileName, Src: string; Tags: TStrings = nil): TDocument;
var
  P: TParser;
begin
  P := TParser.Create;
  P.FTags := Tags;
  try
    Result := P.Run(FileName, Src);
  finally
    P.Free;
  end;
end;

end.
