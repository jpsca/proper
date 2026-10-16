(* minijx: one component's template -> one Python function.

  The function appends pieces of text to a list `_b` (through `_a`, its
  bound `append`) and returns them joined. Blocks whose surrounding code
  depends on what they contain (a for loop needs a Loop object only when
  its body uses `loop`; the function needs the filter dict only when its
  body uses a filter) are generated into their own TWriter first.

  With autoescape, a `{{ }}` renders `_e(value)` (escaped unless it has
  `__html__`) and the body of a `{% filter %}` or of a custom tag is passed as
  `Markup` (`_M`), so it is not escaped again. The content given to a
  component with autoescape is always `Markup`, whatever the mode of the
  caller. Components and fills are appended as they are: they return HTML
  already. *)
unit mjgen;

{$mode objfpc}{$H+}

interface

uses
  SysUtils, mjerrors, mjutil, mjlexer, mjparser, mjexpr, mjcomponent;

type
  TFuncGen = class
  private
    FComp: TComponent;
    FDoc: TDocument;
    FCounter: PInteger; (* shared by the module, so names never clash *)
    FUsesFilters: Boolean;
    FUsesTests: Boolean;
    FUsesTags: Boolean;
    function NextId: string;
    function NewTranslator(const Src: string; Pos: Integer; Scope: TScope): TExprTranslator;
    procedure Absorb(T: TExprTranslator);
    function Expr(const Src: string; Pos: Integer; Scope: TScope): string;
    procedure EmitNodes(W: TWriter; L: TNodeList; Scope: TScope; const App: string);
    procedure EmitBody(W: TWriter; L: TNodeList; Scope: TScope; const App: string);
    procedure EmitBuffer(W: TWriter; const Id: string; L: TNodeList; Scope: TScope);
    procedure EmitIf(W: TWriter; N: TNode; Scope: TScope; const App: string);
    procedure EmitFor(W: TWriter; N: TNode; Scope: TScope; const App: string);
    procedure EmitFilter(W: TWriter; N: TNode; Scope: TScope; const App: string);
    procedure EmitTag(W: TWriter; N: TNode; Scope: TScope; const App: string);
    procedure EmitMacro(W: TWriter; N: TNode; Scope: TScope);
    procedure EmitSlot(W: TWriter; N: TNode; Scope: TScope; const App: string);
    procedure EmitComponent(W: TWriter; N: TNode; Scope: TScope; const App: string);
    procedure CheckCall(N: TNode; Dep: TComponent; HasContent: Boolean; Scope: TScope);
  public
    (* where each line of the generated function comes from; set by Generate *)
    Maps: TSrcMapArray;
    constructor Create(AComp: TComponent; ACounter: PInteger);
    (* the Python function, `def <FuncName>(...)` *)
    function Generate: string;
  end;

implementation

constructor TFuncGen.Create(AComp: TComponent; ACounter: PInteger);
begin
  FComp := AComp;
  FDoc := AComp.Doc;
  FCounter := ACounter;
end;

function TFuncGen.NextId: string;
begin
  Inc(FCounter^);
  Result := IntToStr(FCounter^);
end;

function TFuncGen.NewTranslator(const Src: string; Pos: Integer; Scope: TScope): TExprTranslator;
begin
  Result := TExprTranslator.Create(FDoc.FileName, FDoc.Source, Src, Pos, Scope);
  Result.Autoescape := FComp.Autoescape;
end;

(* What a translated expression needs from the function around it. (`loop`
   is marked on its scope by the translator itself.) *)
procedure TFuncGen.Absorb(T: TExprTranslator);
begin
  FUsesFilters := FUsesFilters or T.UsesFilters;
  FUsesTests := FUsesTests or T.UsesTests;
end;

function TFuncGen.Expr(const Src: string; Pos: Integer; Scope: TScope): string;
var
  T: TExprTranslator;
begin
  T := NewTranslator(Src, Pos, Scope);
  try
    Result := T.Translate;
    Absorb(T);
  finally
    T.Free;
  end;
end;

(* The template range of an expression written at Pos, without the
   whitespace around it: [SrcPos, SrcEnd). *)
procedure ExprRange(const Src: string; Pos: Integer; out SrcPos, SrcEnd: Integer);
var
  i, j: Integer;
begin
  i := 1;
  j := Length(Src);
  while (i <= j) and (Src[i] in WhitespaceChars) do
    Inc(i);
  while (j >= i) and (Src[j] in WhitespaceChars) do
    Dec(j);
  SrcPos := Pos + i - 1;
  SrcEnd := Pos + j;
end;

const
  (* builtin types a `{# def #}` annotation is checked against, as in Jx:
     `name: str`, `items: list[str]` (only `list`); anything else, like
     `user: User` or `str | None`, is not checked *)
  CheckedTypes: array[0..15] of string = ('str', 'int', 'float', 'bool',
    'bytes', 'bytearray', 'complex', 'list', 'dict', 'tuple', 'set',
    'frozenset', 'range', 'slice', 'memoryview', 'type');

(* The builtin type to check an annotation against, or ''. *)
function CheckedType(const Annotation: string): string;
var
  A: string;
  i: Integer;
begin
  Result := '';
  A := Trim(Annotation);
  i := Pos('[', A);
  if i > 0 then
  begin
    if not EndsWith(A, ']') then
      Exit;
    A := Trim(Copy(A, 1, i - 1));
  end;
  if InList(A, CheckedTypes) then
    Result := A;
end;

(* A default that is a literal Python keeps as it is: a number, a string,
   True, False or None. Anything else (`[]`, `{"a": 1}`, `1 + 2`) is
   evaluated on each call, so a list is never shared between renders. *)
function IsConstDefault(const Default: string): Boolean;
var
  D: string;
  i: Integer;
  Q: Char;
begin
  D := Trim(Default);
  if D = '' then
    Exit(False);
  if InList(D, ['True', 'False', 'None']) then
    Exit(True);
  if D[1] in ['''', '"'] then
  begin
    Q := D[1];
    if (Length(D) < 2) or (D[Length(D)] <> Q) then
      Exit(False);
    for i := 2 to Length(D) - 1 do
      if D[i] in [Q, '\'] then
        Exit(False);
    Exit(True);
  end;
  for i := 1 to Length(D) do
    if not (D[i] in ['0'..'9', '.', '_', '-', '+', 'e', 'E']) then
      Exit(False);
  Result := D[Length(D)] in ['0'..'9', '.'];
end;

(* Text for a Python f-string: its literal part, with braces doubled. *)
function FStringText(const S: string): string;
var
  i: Integer;
  B: TBuf;
begin
  B := TBuf.Create;
  try
    for i := 1 to Length(S) do
      case S[i] of
        '{': B.Add('{{');
        '}': B.Add('}}');
        '\': B.Add('\\');
        '''': B.Add('\''');
        #10: B.Add('\n');
        #13: B.Add('\r');
        #9: B.Add('\t');
        #0..#8, #11, #12, #14..#31: B.Add('\x' + IntToHex(Ord(S[i]), 2));
      else
        B.Add(S[i]);
      end;
    Result := B.Join;
  finally
    B.Free;
  end;
end;

procedure TFuncGen.EmitNodes(W: TWriter; L: TNodeList; Scope: TScope; const App: string);
var
  i: Integer;
  N: TNode;
  T: TExprTranslator;
  Name, Value: string;
  (* consecutive text and `{{ }}` outputs, written with one append *)
  Run: TStringArray;    (* text, or Python expression *)
  RunIsExpr: array of Boolean;
  RunEscape: array of Boolean; (* the expression goes through `_e` *)
  RunPos, RunEnd: array of Integer; (* the expression's range in the template *)
  Text: string;         (* text not added to Run yet *)
  Safe: Boolean;
  SP, SE: Integer;

  procedure AddText;
  begin
    if Text = '' then
      Exit;
    SetLength(Run, Length(Run) + 1);
    SetLength(RunIsExpr, Length(RunIsExpr) + 1);
    SetLength(RunEscape, Length(RunEscape) + 1);
    SetLength(RunPos, Length(RunPos) + 1);
    SetLength(RunEnd, Length(RunEnd) + 1);
    Run[High(Run)] := Text;
    RunIsExpr[High(RunIsExpr)] := False;
    RunEscape[High(RunEscape)] := False;
    Text := '';
  end;

  procedure AddExpr(const E: string; Escape: Boolean; APos, AEnd: Integer);
  begin
    AddText;
    SetLength(Run, Length(Run) + 1);
    SetLength(RunIsExpr, Length(RunIsExpr) + 1);
    SetLength(RunEscape, Length(RunEscape) + 1);
    SetLength(RunPos, Length(RunPos) + 1);
    SetLength(RunEnd, Length(RunEnd) + 1);
    Run[High(Run)] := E;
    RunIsExpr[High(RunIsExpr)] := True;
    RunEscape[High(RunEscape)] := Escape;
    RunPos[High(RunPos)] := APos;
    RunEnd[High(RunEnd)] := AEnd;
  end;

  (* One piece: `_a('text')` or `_a(_s(expr))` (`_a(_e(expr))` to escape
     it). More: an f-string, which builds the text in one go instead of one
     call per piece; `!s` is the same str() the single case uses, and `_e`
     already returns a str. *)
  procedure FlushRun;
  var
    k, Col: Integer;
    F, Prefix: string;
    Spans: TSpanArray;
  begin
    AddText;
    if Length(Run) = 1 then
    begin
      if RunEscape[0] then
        W.Line(App + '(_e(' + Run[0] + '))', RunPos[0], RunEnd[0])
      else if RunIsExpr[0] then
        W.Line(App + '(_s(' + Run[0] + '))', RunPos[0], RunEnd[0])
      else
        W.Line(App + '(' + PyStr(Run[0]) + ')');
    end
    else if Length(Run) > 1 then
    begin
      (* each expression's columns in the line, so an error can be traced
         to the one that failed *)
      Prefix := App + '(f''';
      F := '';
      SetLength(Spans, 0);
      for k := 0 to High(Run) do
      begin
        Col := Length(Prefix) + Length(F);
        if RunEscape[k] then
          F := F + '{_e(' + Run[k] + ')}'
        else if RunIsExpr[k] then
          F := F + '{(' + Run[k] + ')!s}'
        else
          F := F + FStringText(Run[k]);
        if RunIsExpr[k] then
        begin
          SetLength(Spans, Length(Spans) + 1);
          Spans[High(Spans)].Col := Col;
          Spans[High(Spans)].EndCol := Length(Prefix) + Length(F);
          Spans[High(Spans)].SrcPos := RunPos[k];
          Spans[High(Spans)].SrcEnd := RunEnd[k];
        end;
      end;
      W.LineSpans(Prefix + F + ''')', Spans);
    end;
    SetLength(Run, 0);
    SetLength(RunIsExpr, 0);
    SetLength(RunEscape, 0);
    SetLength(RunPos, 0);
    SetLength(RunEnd, 0);
  end;

begin
  (* macros can call the ones defined after them, as in Jinja: their names
     are local from the start of the block *)
  for i := 0 to L.Count - 1 do
    if (L[i].Kind = nkMacro) and (L[i].Name <> '') then
      Scope.Bind(L[i].Name);
  Text := '';
  SetLength(Run, 0);
  SetLength(RunIsExpr, 0);
  SetLength(RunEscape, 0);
  SetLength(RunPos, 0);
  SetLength(RunEnd, 0);
  for i := 0 to L.Count - 1 do
  begin
    N := L[i];
    case N.Kind of
      nkText, nkRaw:
        begin
          Text := Text + N.Text;
          Continue;
        end;
      nkOutput:
        begin
          ExprRange(N.Expr, N.ExprPos, SP, SE);
          if FComp.Autoescape then
          begin
            T := NewTranslator(N.Expr, N.ExprPos, Scope);
            try
              Value := T.TranslateOutput(Safe);
              Absorb(T);
            finally
              T.Free;
            end;
            AddExpr(Value, not Safe, SP, SE);
          end
          else
            AddExpr(Expr(N.Expr, N.ExprPos, Scope), False, SP, SE);
          Continue;
        end;
      nkComment:
        Continue;
    end;
    FlushRun;
    case N.Kind of
      nkIf:
        EmitIf(W, N, Scope, App);
      nkFor:
        EmitFor(W, N, Scope, App);
      nkSet:
        begin
          T := NewTranslator(N.Expr, N.ExprPos, Scope);
          try
            T.TranslateSet(Name, Value);
            Absorb(T);
          finally
            T.Free;
          end;
          (* after the value, which may read the name's previous value *)
          ExprRange(N.Expr, N.ExprPos, SP, SE);
          W.Line(Scope.Bind(Name) + ' = ' + Value, SP, SE);
        end;
      nkDo:
        begin
          ExprRange(N.Expr, N.ExprPos, SP, SE);
          W.Line(Expr(N.Expr, N.ExprPos, Scope), SP, SE);
        end;
      nkFilter:
        EmitFilter(W, N, Scope, App);
      nkTag:
        EmitTag(W, N, Scope, App);
      nkMacro:
        EmitMacro(W, N, Scope);
      nkSlot:
        EmitSlot(W, N, Scope, App);
      nkComponent:
        EmitComponent(W, N, Scope, App);
      nkFill:
        CompileError(FDoc.FileName, FDoc.Source, N.Pos, 'Unexpected `{% fill %}`');
    end;
  end;
  FlushRun;
end;

(* The body of a Python block. A body can have nodes and still produce no
   code (comments, text trimmed away by whitespace control), and an empty
   Python block is a syntax error, hence the `pass`. *)
procedure TFuncGen.EmitBody(W: TWriter; L: TNodeList; Scope: TScope; const App: string);
var
  Before: Integer;
begin
  Before := W.Count;
  EmitNodes(W, L, Scope, App);
  if W.Count = Before then
    W.Line('pass');
end;

(* `_b<id> = []; _a<id> = _b<id>.append; <nodes>`: a list of its own, for a
   block whose rendered text is used as a value. *)
procedure TFuncGen.EmitBuffer(W: TWriter; const Id: string; L: TNodeList; Scope: TScope);
begin
  W.Line('_b' + Id + ' = []');
  W.Line('_a' + Id + ' = _b' + Id + '.append');
  EmitNodes(W, L, Scope, '_a' + Id);
end;

procedure TFuncGen.EmitIf(W: TWriter; N: TNode; Scope: TScope; const App: string);
var
  i, SP, SE: Integer;
  B: TBranch;
begin
  for i := 0 to High(N.Branches) do
  begin
    B := N.Branches[i];
    ExprRange(B.Cond, B.CondPos, SP, SE);
    if B.Cond = '' then
      W.Line('else:')
    else if i = 0 then
      W.Line('if ' + Expr(B.Cond, B.CondPos, Scope) + ':', SP, SE)
    else
      W.Line('elif ' + Expr(B.Cond, B.CondPos, Scope) + ':', SP, SE);
    Inc(W.Indent);
    EmitBody(W, B.Body, Scope, App);
    Dec(W.Indent);
  end;
end;

procedure TFuncGen.EmitFor(W: TWriter; N: TNode; Scope: TScope; const App: string);
var
  T: TExprTranslator;
  Target, Iter, Cond, Id, IterExpr, LoopVar, ElseFlag, BodyApp: string;
  Names: TStringArray;
  Recursive, HasElse: Boolean;
  BodyScope: TScope;
  Depth, SP, SE: Integer;
  BodyW, ElseW: TWriter;
begin
  Id := NextId;
  BodyScope := TScope.Create(Scope);
  T := NewTranslator(N.Expr, N.ExprPos, Scope);
  try
    T.TranslateFor(Target, Names, Iter, Cond, Recursive, Scope, BodyScope);
    Absorb(T);
  finally
    T.Free;
  end;
  HasElse := (N.ElseBody <> nil) and (N.ElseBody.Count > 0);
  ExprRange(N.Expr, N.ExprPos, SP, SE);
  LoopVar := '_l' + Id;
  ElseFlag := '_e' + Id;
  (* a recursive loop is a nested function that appends to a list of its own *)
  if Recursive then
  begin
    Depth := 2;
    BodyApp := '_ra' + Id;
  end
  else
  begin
    Depth := 1;
    BodyApp := App;
  end;

  BodyW := TWriter.Create(W.Indent + Depth);
  ElseW := TWriter.Create(W.Indent + Depth);
  try
    BodyScope.LoopVar := LoopVar;

    (* the body first: it tells whether the loop needs a Loop object *)
    if HasElse then
      BodyW.Line(ElseFlag + ' = False');
    EmitBody(BodyW, N.Body, BodyScope, BodyApp);
    if HasElse then
      EmitBody(ElseW, N.ElseBody, Scope, BodyApp);

    if Cond <> '' then
      IterExpr := '(' + Target + ' for ' + Target + ' in ' + Iter + ' if ' + Cond + ')'
    else
      IterExpr := Iter;

    if Recursive then
    begin
      W.Line('def _r' + Id + '(_iter, _depth0=0):', SP, SE);
      Inc(W.Indent);
      W.Line('_rb' + Id + ' = []');
      W.Line('_ra' + Id + ' = _rb' + Id + '.append');
      if Cond <> '' then
        W.Line(LoopVar + ' = Loop((' + Target + ' for ' + Target + ' in _iter if ' + Cond +
          '), _depth0, _r' + Id + ')', SP, SE)
      else
        W.Line(LoopVar + ' = Loop(_iter, _depth0, _r' + Id + ')', SP, SE);
      if HasElse then
        W.Line(ElseFlag + ' = True');
    end
    else
    begin
      if HasElse then
        W.Line(ElseFlag + ' = True');
      if BodyScope.LoopUsed then
        W.Line(LoopVar + ' = Loop(' + IterExpr + ')', SP, SE);
    end;
    if Recursive or BodyScope.LoopUsed then
      W.Line('for ' + Target + ' in ' + LoopVar + ':', SP, SE)
    else
      W.Line('for ' + Target + ' in ' + IterExpr + ':', SP, SE);
    W.Append(BodyW);
    if HasElse then
    begin
      W.Line('if ' + ElseFlag + ':');
      W.Append(ElseW);
    end;
    if Recursive then
    begin
      (* `{{ loop(children) }}` renders this: markup with autoescape, as
         Jinja's recursive loop *)
      if FComp.Autoescape then
        W.Line('return _M("".join(_rb' + Id + '))')
      else
        W.Line('return "".join(_rb' + Id + ')');
      Dec(W.Indent);
      W.Line(App + '(_r' + Id + '(' + Iter + '))', SP, SE);
    end;
  finally
    ElseW.Free;
    BodyW.Free;
    BodyScope.Free;
  end;
end;

(* The text a block rendered, as a value: markup with autoescape. *)
function BlockText(const Id: string; Autoescape: Boolean): string;
begin
  Result := '"".join(_b' + Id + ')';
  if Autoescape then
    Result := '_M(' + Result + ')';
end;

(* `_a(_s(value))`, or `_a(_e(value))` with autoescape. *)
function OutputLine(const App, Value: string; Autoescape: Boolean): string;
begin
  if Autoescape then
    Result := App + '(_e(' + Value + '))'
  else
    Result := App + '(_s(' + Value + '))';
end;

procedure TFuncGen.EmitFilter(W: TWriter; N: TNode; Scope: TScope; const App: string);
var
  Id, Chain: string;
  SP, SE: Integer;
  T: TExprTranslator;
begin
  Id := NextId;
  EmitBuffer(W, Id, N.Body, Scope);
  T := NewTranslator(N.Expr, N.ExprPos, Scope);
  try
    Chain := T.TranslateFilterChain(BlockText(Id, FComp.Autoescape));
    Absorb(T);
  finally
    T.Free;
  end;
  ExprRange(N.Expr, N.ExprPos, SP, SE);
  W.Line(OutputLine(App, Chain, FComp.Autoescape), SP, SE);
end;

(* `{% cache key, expires_in=60 %}body{% endcache %}`: the body becomes a
   function, which the tag's function calls only if it needs it:
   `_tags['cache'](key, expires_in=60, caller=_tag5, template='page.jx')` *)
procedure TFuncGen.EmitTag(W: TWriter; N: TNode; Scope: TScope; const App: string);
var
  Id, Args, Call: string;
  SP, SE: Integer;
  T: TExprTranslator;
  BodyScope: TScope;
begin
  Id := NextId;
  W.Line('def _tag' + Id + '():');
  Inc(W.Indent);
  BodyScope := TScope.Create(Scope);
  BodyScope.IsFunc := True;
  try
    EmitBuffer(W, Id, N.Body, BodyScope);
  finally
    BodyScope.Free;
  end;
  W.Line('return ' + BlockText(Id, FComp.Autoescape));
  Dec(W.Indent);

  if N.Parens then
    T := NewTranslator(N.Expr, N.ExprPos, Scope)
  else
    (* written without parentheses: parsed as if it had them, with the
       offsets still pointing into the file *)
    T := NewTranslator('(' + N.Expr + ')', N.ExprPos - 1, Scope);
  try
    Args := T.TranslateTagArgs;
    Absorb(T);
  finally
    T.Free;
  end;
  if Args <> '' then
    Args := Args + ', ';
  FUsesTags := True;
  Call := '_tags[' + PyStr(N.Name) + '](' + Args + 'caller=_tag' + Id +
    ', template=' + PyStr(FComp.RelPath) + ')';
  (* the tag's arguments, or the line of the tag if it has none *)
  ExprRange(N.Expr, N.ExprPos, SP, SE);
  if SE <= SP then
  begin
    SP := N.Pos;
    SE := 0;
  end;
  (* not escaped, as the `{% call %}` blocks Jinja extensions build *)
  W.Line(App + '(_s(' + Call + '))', SP, SE);
end;

(* `{% macro card(title, cls="x") %}body{% endmacro %}`: a nested function,
   defined where the macro is, so it sees the variables of the component
   when it is called, and can call itself. Defaults are evaluated on each
   call, as in Jinja; `UNDEFINED` marks the ones not given.

     def card(title, cls=UNDEFINED):
         if cls is UNDEFINED:
             cls = "x"
         ...
         return _M("".join(_b7))                 # "".join(...) without autoescape
*)
procedure TFuncGen.EmitMacro(W: TWriter; N: TNode; Scope: TScope);
var
  T: TExprTranslator;
  MacroScope: TScope;
  Name, PyName, Sig, Id: string;
  Params, Defaults: TStringArray;
  i, SP, SE: Integer;
begin
  MacroScope := TScope.Create(Scope);
  try
    MacroScope.IsFunc := True;
    MacroScope.IsMacro := True;
    T := NewTranslator(N.Expr, N.ExprPos, Scope);
    try
      T.TranslateMacroSig(MacroScope, Name, Params, Defaults);
      Absorb(T);
    finally
      T.Free;
    end;
    (* bound before the body, so the body can call the macro *)
    PyName := Scope.Bind(Name);

    Sig := '';
    for i := 0 to High(Params) do
    begin
      if i > 0 then
        Sig := Sig + ', ';
      Sig := Sig + Params[i];
      if Defaults[i] <> '' then
        Sig := Sig + '=UNDEFINED';
    end;
    ExprRange(N.Expr, N.ExprPos, SP, SE);
    W.Line('def ' + PyName + '(' + Sig + '):', SP, SE);
    Inc(W.Indent);
    for i := 0 to High(Params) do
      if Defaults[i] <> '' then
      begin
        W.Line('if ' + Params[i] + ' is UNDEFINED:', SP, SE);
        W.Line('    ' + Params[i] + ' = ' + Defaults[i], SP, SE);
      end;
    Id := NextId;
    EmitBuffer(W, Id, N.Body, MacroScope);
    W.Line('return ' + BlockText(Id, FComp.Autoescape));
    Dec(W.Indent);
  finally
    MacroScope.Free;
  end;
end;

procedure TFuncGen.EmitSlot(W: TWriter; N: TNode; Scope: TScope; const App: string);
begin
  W.Line('if ' + PyStr(N.Name) + ' in _fills:');
  Inc(W.Indent);
  W.Line(App + '(_fills[' + PyStr(N.Name) + ']())', N.Pos, 0);
  Dec(W.Indent);
  if N.Body.Count > 0 then
  begin
    W.Line('else:');
    Inc(W.Indent);
    EmitBody(W, N.Body, Scope, App);
    Dec(W.Indent);
  end;
end;

(* What can be known about a component call at compile time, checked with
   the signature of the component: a required argument missing, or a
   literal of a type its annotation does not accept (as `isinstance` would
   not). Values computed when rendering are checked then (InvalidPropType). *)
procedure TFuncGen.CheckCall(N: TNode; Dep: TComponent; HasContent: Boolean; Scope: TScope);
var
  i, k: Integer;
  Name, Expected, Got: string;
  Given, Spread: Boolean;
  T: TExprTranslator;
begin
  Spread := False;
  for i := 0 to High(N.Attrs) do
    if ReplaceChar(N.Attrs[i].Name, '-', '_') = 'attrs' then
      Spread := True;

  for k := 0 to High(Dep.Args) do
  begin
    if Dep.Args[k].HasDefault or Spread then
      Continue;
    Name := Dep.Args[k].Name;
    Given := (Name = 'content') and HasContent;
    for i := 0 to High(N.Attrs) do
      if ReplaceChar(N.Attrs[i].Name, '-', '_') = Name then
        Given := True;
    if not Given then
      CompileError(FDoc.FileName, FDoc.Source, N.Pos,
        '`<' + N.Name + '>` needs the argument `' + Name + '` (' + Dep.RelPath + ')');
  end;

  for i := 0 to High(N.Attrs) do
  begin
    Name := ReplaceChar(N.Attrs[i].Name, '-', '_');
    for k := 0 to High(Dep.Args) do
    begin
      if Dep.Args[k].Name <> Name then
        Continue;
      Expected := CheckedType(Dep.Args[k].Annotation);
      if Expected = '' then
        Break;
      case N.Attrs[i].Kind of
        akString: Got := 'str';
        akFlag: Got := 'bool';
      else
        T := NewTranslator(N.Attrs[i].Value, N.Attrs[i].ValuePos, Scope);
        try
          Got := T.LiteralType;
        finally
          T.Free;
        end;
      end;
      (* as `isinstance`: a bool is an int *)
      if (Got <> '') and (Got <> Expected) and not ((Got = 'bool') and (Expected = 'int')) then
        CompileError(FDoc.FileName, FDoc.Source, N.Attrs[i].Pos,
          '`' + N.Attrs[i].Name + '` of `<' + N.Name + '>` expects ' + Expected +
          ', got ' + Got + ' (' + Dep.RelPath + ')');
      Break;
    end;
  end;
end;

procedure TFuncGen.EmitComponent(W: TWriter; N: TNode; Scope: TScope; const App: string);
var
  Dep: TComponent;
  i: Integer;
  A: TAttr;
  Args, Kw, Fills, Call, Id, FillId, Name, Value, Spread: string;
  FillScope: TScope;
  F: TNode;
  HasContent, Plain: Boolean;
begin
  Dep := FComp.FindDep(N.Name);
  if Dep = nil then
    CompileError(FDoc.FileName, FDoc.Source, N.Pos,
      'Component `' + N.Name + '` is not imported; add `{# import "..." as ' + N.Name + ' #}`');

  Id := NextId;
  (* fills become closures defined before the call, rendered only if the
     component reaches the slot *)
  Fills := '';
  for i := 0 to N.Fills.Count - 1 do
  begin
    F := N.Fills[i];
    FillId := NextId;
    W.Line('def _fill' + FillId + '():');
    Inc(W.Indent);
    FillScope := TScope.Create(Scope);
    FillScope.IsFunc := True;
    try
      EmitBuffer(W, FillId, F.Body, FillScope);
    finally
      FillScope.Free;
    end;
    W.Line('return "".join(_b' + FillId + ')');
    Dec(W.Indent);
    Fills := Fills + PyStr(F.Name) + ': _fill' + FillId + ', ';
  end;

  (* the default content, rendered eagerly into its own list *)
  HasContent := N.Body.HasContent;
  CheckCall(N, Dep, HasContent, Scope);
  if HasContent then
    EmitBuffer(W, Id, N.Body, Scope);

  (* Attributes go as plain keyword arguments, much cheaper than building
     and unpacking a dict. Names Python cannot take that way (`class`,
     `@click`) go in a `**{...}`, and so does everything when one of them is
     a name the function itself uses, to keep what that does as it was. (The
     lexer already refused repeated names.) *)
  Plain := True;
  Spread := '';
  for i := 0 to High(N.Attrs) do
    if InList(ReplaceChar(N.Attrs[i].Name, '-', '_'), ['content', '_globals', '_fills']) then
      Plain := False;
  Args := '';
  Kw := '';
  for i := 0 to High(N.Attrs) do
  begin
    A := N.Attrs[i];
    Name := ReplaceChar(A.Name, '-', '_');
    case A.Kind of
      akFlag: Value := 'True';
      akString: Value := A.Value;
    else
      Value := Expr(A.Value, A.ValuePos, Scope);
    end;
    if Name = 'attrs' then
      Spread := Value
    else if Plain and IsPyIdentifier(Name) then
      Args := Args + Name + '=' + Value + ', '
    else
      Kw := Kw + PyStr(Name) + ': ' + Value + ', ';
  end;

  if Spread <> '' then
  begin
    (* `attrs={{ attrs }}`, as Jx: the forwarded attributes also fill the
       arguments the component declares, and the explicit ones win *)
    Kw := '';
    for i := 0 to High(N.Attrs) do
    begin
      A := N.Attrs[i];
      Name := ReplaceChar(A.Name, '-', '_');
      if Name = 'attrs' then
        Continue;
      case A.Kind of
        akFlag: Value := 'True';
        akString: Value := A.Value;
      else
        Value := Expr(A.Value, A.ValuePos, Scope);
      end;
      Kw := Kw + PyStr(Name) + ': ' + Value + ', ';
    end;
    Call := Dep.FuncName + '(**_merge_attrs(' + Spread + ', {' + Kw + '}), ';
  end
  else
  begin
    Call := Dep.FuncName + '(' + Args;
    if Kw <> '' then
      Call := Call + '**{' + Copy(Kw, 1, Length(Kw) - 2) + '}, ';
  end;
  if HasContent then
    (* The content is written by the template author, not data, so it is
       markup for a component with autoescape whatever the mode of this
       one: its values were already escaped here, or not by choice. *)
    Call := Call + 'content=' + BlockText(Id, Dep.Autoescape) + ', ';
  if Fills <> '' then
    Call := Call + '_fills={' + Copy(Fills, 1, Length(Fills) - 2) + '}, ';
  Call := Call + '_globals=_globals)';
  (* `<Card`: the tag, where the arguments are *)
  W.Line(App + '(' + Call + ')', N.Pos, N.Pos + 1 + Length(N.Name));
end;

function TFuncGen.Generate: string;
var
  Scope: TScope;
  Sig, Check, DefLine: string;
  i, DefEnd: Integer;
  HasContentArg, HasAttrsArg: Boolean;
  W, BodyW: TWriter;
begin
  Scope := TScope.Create(nil);
  W := TWriter.Create(0);
  BodyW := TWriter.Create(1);
  try
    Sig := '*';
    HasContentArg := False;
    HasAttrsArg := False;
    for i := 0 to High(FComp.Args) do
    begin
      Sig := Sig + ', ' + FComp.Args[i].Name;
      if FComp.Args[i].Annotation <> '' then
        Sig := Sig + ': ' + FComp.Args[i].Annotation;
      if FComp.Args[i].HasDefault then
        if IsConstDefault(FComp.Args[i].Default) then
          Sig := Sig + '=' + FComp.Args[i].Default
        else
          Sig := Sig + '=UNDEFINED';
      Scope.Add(FComp.Args[i].Name);
      HasContentArg := HasContentArg or (FComp.Args[i].Name = 'content');
      HasAttrsArg := HasAttrsArg or (FComp.Args[i].Name = 'attrs');
    end;
    if not HasContentArg then
      Sig := Sig + ', content=""';
    Sig := Sig + ', _globals=None, _fills=None, **_extra';
    Scope.Add('content');
    Scope.Add('attrs');
    Scope.Add('_globals');
    Scope.Add('_fills');

    (* the body first: it tells whether the function needs the filters and
       tests *)
    BodyW.Line('_b = []');
    BodyW.Line('_a = _b.append');
    EmitNodes(BodyW, FDoc.Body, Scope, '_a');
    (* like Jx's Component.render: the output never starts with whitespace *)
    BodyW.Line('return "".join(_b).lstrip()');

    W.Line('def ' + FComp.FuncName + '(' + Sig + '):');
    Inc(W.Indent);
    W.Line('if _globals is None:');
    W.Line('    _globals = {}');
    W.Line('if _fills is None:');
    W.Line('    _fills = {}');
    (* defaults evaluated on each call, then the types, as Jx checks them:
       the default values too. An error here is the `{# def #}` line. *)
    DefEnd := 0;
    if FDoc.HasDef then
      DefEnd := FDoc.DefPos + Length(TrimRight(FDoc.DefExpr));
    for i := 0 to High(FComp.Args) do
      if FComp.Args[i].HasDefault and not IsConstDefault(FComp.Args[i].Default) then
      begin
        DefLine := FComp.Args[i].Name + ' = ' + FComp.Args[i].Default;
        W.Line('if ' + FComp.Args[i].Name + ' is UNDEFINED:', FDoc.DefPos, DefEnd);
        W.Line('    ' + DefLine, FDoc.DefPos, DefEnd);
      end;
    for i := 0 to High(FComp.Args) do
    begin
      Check := CheckedType(FComp.Args[i].Annotation);
      if Check = '' then
        Continue;
      W.Line('if not isinstance(' + FComp.Args[i].Name + ', ' + Check + '):',
        FDoc.DefPos, DefEnd);
      W.Line('    _invalid_prop(' + PyStr(FComp.RelPath) + ', ' + PyStr(FComp.Args[i].Name) +
        ', ' + Check + ', ' + FComp.Args[i].Name + ')', FDoc.DefPos, DefEnd);
    end;
    if FComp.UsesAttrs and not HasAttrsArg then
      W.Line('attrs = _extra["attrs"] if isinstance(_extra.get("attrs"), Attrs) else Attrs(_extra)');
    (* custom filters and tests come from the catalog, through `_globals` *)
    if FUsesFilters and FComp.Autoescape then
      W.Line('_f = _globals.get("__minijx_filters_ae__", _FILTERS_AE)')
    else if FUsesFilters then
      W.Line('_f = _globals.get("__minijx_filters__", _FILTERS)');
    if FUsesTests then
      W.Line('_t = _globals.get("__minijx_tests__", _TESTS)');
    (* the functions of the custom tags come from the catalog *)
    if FUsesTags then
      W.Line('_tags = _globals.get("__minijx_tags__", _NO_TAGS)');
    W.Append(BodyW);
    Result := W.Text;
    Maps := W.Maps;
  finally
    BodyW.Free;
    W.Free;
    Scope.Free;
  end;
end;

end.
