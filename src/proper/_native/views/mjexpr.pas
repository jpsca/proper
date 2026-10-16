(* minijx: Jinja expression -> Python expression.

  Two steps. The parser builds a small tree (TExpr) with Jinja's precedence,
  lowest first:
    a if b else c, or, and, not, comparisons, + -, ~, * / // %, **, unary,
    primary . [] (), | filter, is test.
  The generator walks the tree and writes Python, resolving each name
  against the scope it is used in:
  - names bound in the template (arguments, set, for targets, content,
    attrs) are emitted as they are;
  - `loop` becomes the Python variable of the innermost for loop;
  - a short list of Python builtins passes through;
  - any other name is a global: `_globals["name"]`.
  Constructs that need to know what their operand is (`x | default`,
  `x is defined`, `attrs.x`, `{% call f(a) %}`) look at its node. *)
unit mjexpr;

{$mode objfpc}{$H+}

interface

uses
  SysUtils, Classes, mjerrors, mjutil;

type
  TScope = class
  private
    FNames: TStringList;
    FPyNames: TStringList; (* `name=python name` for the names Bind renamed *)
    FRenamed: Integer;     (* on the root scope: renames given out, for unique names *)
  public
    Parent: TScope;
    LoopVar: string;   (* Python name the template's `loop` refers to, '' if none *)
    LoopUsed: Boolean; (* set on the scope that owns LoopVar when `loop` is used *)
    (* the scope is the body of a nested Python function (a fill, the body of
       a custom tag, a recursive loop): an assignment in it makes a local of
       that function *)
    IsFunc: Boolean;
    IsMacro: Boolean; (* the body of a macro *)
    constructor Create(AParent: TScope);
    (* inside the body of a macro, at any depth *)
    function InMacro: Boolean;
    destructor Destroy; override;
    procedure Add(const Name: string);
    function IsLocal(const Name: string): Boolean;
    (* The Python name a template name refers to here: itself, or the name
       Bind gave it. *)
    function PyName(const Name: string): string;
    (* Bind a name assigned in this scope (`set`, a for target) and return
       the Python name to assign. In a nested function, a name the outer
       function has is renamed: otherwise Python would make it local to the
       whole nested function, and reading the outer value before the
       assignment would raise UnboundLocalError. *)
    function Bind(const Name: string): string;
    (* the innermost scope with a loop variable, or nil *)
    function LoopScope: TScope;
  end;

  TExprKind = (
    ekName,    (* Value: the name *)
    ekConst,   (* Value: Python literal: a number, True, False, None *)
    ekStr,     (* Value: string literal(s) as written *)
    ekList,    (* Items *)
    ekTuple,   (* Items; Flag: written with a trailing comma *)
    ekDict,    (* Items: key, value, key, value... *)
    ekGetAttr, (* Items[0].Value; Flag: Value is a number (`x.0`) *)
    ekGetItem, (* Items[0][Items[1]] *)
    ekSlice,   (* Items[0][Items[1]:Items[2](:Items[3])]; nil parts are empty; Flag: has a step *)
    ekCall,    (* Items[0](Args) *)
    ekFilter,  (* Items[0] | Value(Args) *)
    ekTest,    (* Items[0] is [not] Value(Args); Flag: negated *)
    ekUnary,   (* Value Items[0], Value is `-` or `+` *)
    ekNot,     (* not Items[0] *)
    ekBinary,  (* Items[0] Value Items[1]: + - * / // % ** and or *)
    ekConcat,  (* Items[0] ~ Items[1] ~ ... *)
    ekCompare, (* Items[0] Ops[0] Items[1] Ops[1] Items[2] ... *)
    ekCond     (* Items[0] if Items[1] else Items[2] (nil: Jinja's "") *)
  );

  TArgKind = (akPositional, akKeyword, akStar, akDoubleStar);

  TExpr = class;

  TCallArg = record
    Kind: TArgKind;
    Name: string; (* akKeyword *)
    Value: TExpr;
  end;

  TExpr = class
  public
    Kind: TExprKind;
    Pos: Integer; (* 1-based offset in the expression source *)
    Value: string;
    Flag: Boolean;
    Items: array of TExpr;
    Ops: TStringArray;
    Args: array of TCallArg;
    HasArgs: Boolean; (* ekFilter/ekTest: written with arguments *)
    procedure Add(E: TExpr);
  end;

  TXTokKind = (xkName, xkInt, xkFloat, xkStr, xkOp, xkEOF);

  TExprTranslator = class
  private
    FFile: string;
    FFileSrc: string;
    FSrc: string;
    FBase: Integer; (* 1-based offset of FSrc[1] in FFileSrc *)
    FScope: TScope;
    FNodes: TList;  (* every node created, freed with the translator *)
    (* tokens *)
    FPos: Integer;
    FTokKind: TXTokKind;
    FTokVal: string;
    FTokPos: Integer;
    procedure Fail(TokPos: Integer; const Msg: string);
    procedure Next;
    function IsName(const V: string): Boolean;
    function IsOp(const V: string): Boolean;
    procedure Expect(const V: string);
    function Node(AKind: TExprKind; APos: Integer; const AValue: string = ''): TExpr;
    (* parser *)
    function ParseExpression: TExpr;
    function ParseOr: TExpr;
    function ParseAnd: TExpr;
    function ParseNot: TExpr;
    function ParseCompare: TExpr;
    function ParseMath1: TExpr;
    function ParseConcat: TExpr;
    function ParseMath2: TExpr;
    function ParsePow: TExpr;
    function ParseUnary(WithFilter: Boolean = True): TExpr;
    function ParsePrimary: TExpr;
    function ParsePostfix(E: TExpr): TExpr;
    function ParseFilterExpr(E: TExpr): TExpr;
    function ParseFilter(Subject: TExpr): TExpr;
    function ParseCallArgs(E: TExpr): Boolean;
    function ParseSequence(E: TExpr; const Close: string): Boolean;
    function ParseEnd(const Where: string): Boolean;
    (* generator *)
    function Gen(E: TExpr): string;
    function GenName(E: TExpr): string;
    function GenArgs(E: TExpr): string;
    function GenSafe(E: TExpr): string;
    function GenDefined(E: TExpr): string;
    function GenTest(E: TExpr): string;
    function FilterCall(const Name, Subject, Args: string): string;
    function IsRuntimeObject(E: TExpr): Boolean;
    function IsGlobal(E: TExpr): Boolean;
  public
    UsesLoop: Boolean;
    (* the expression calls a filter / a test looked up by name *)
    UsesFilters: Boolean;
    UsesTests: Boolean;
    (* set by the caller: the component is compiled with autoescape, so
       `a ~ b` keeps markup, as Jinja's `markup_join` *)
    Autoescape: Boolean;
    constructor Create(const AFile, AFileSrc, ASrc: string; ABase: Integer;
      AScope: TScope);
    destructor Destroy; override;
    (* Translate the whole source as one expression. *)
    function Translate: string;
    (* The same, for a `{{ }}`. Safe: the value never needs escaping (a
       number, True/False/None) or it is the result of a filter trusted to
       return markup (`e`, `escape`, `forceescape`, `safe`). *)
    function TranslateOutput(out Safe: Boolean): string;
    (* `a, b` or `(a, b)` or `a`: Python target plus the names it binds. *)
    function TranslateTarget(out Names: TStringArray): string;
    (* For `{% for target in iter [if cond] [recursive] %}`. The target
       names are bound in BodyScope (a recursive loop's body is a function
       of its own), and Target uses their Python names. *)
    procedure TranslateFor(out Target: string; out Names: TStringArray;
      out Iter: string; out Cond: string; out Recursive: Boolean;
      IterScope, BodyScope: TScope);
    (* For `{% set name = expr %}`. *)
    procedure TranslateSet(out Name: string; out Value: string);
    (* `{% filter upper|replace("a", "b") %}` applied to Subject. *)
    function TranslateFilterChain(const Subject: string): string;
    (* The arguments of a custom tag, `(a, b=1)`, as a Python argument list. *)
    function TranslateTagArgs: string;
    (* The Python type of the expression if it is a literal (`"x"` -> str,
       `3` -> int, `-1.5` -> float, `true` -> bool, `none` -> NoneType,
       `[..]` -> list, `{..}` -> dict, `(a, b)` -> tuple), else ''. *)
    function LiteralType: string;
    (* `name(a, b=default)` of a macro. The parameters are added to
       MacroScope, and each default is Python code evaluated there ('' for
       none), so it can use the parameters before it and the variables of
       the component, when the macro is called, as in Jinja. *)
    procedure TranslateMacroSig(MacroScope: TScope; out Name: string;
      out Params, Defaults: TStringArray);
  end;

const
  PyBuiltins: array[0..22] of string = ('range', 'dict', 'list', 'tuple', 'set',
    'len', 'min', 'max', 'sum', 'abs', 'round', 'str', 'int', 'float', 'bool',
    'zip', 'enumerate', 'sorted', 'reversed', 'isinstance', 'getattr', 'hasattr',
    'print');

implementation

(* TScope *)

constructor TScope.Create(AParent: TScope);
begin
  Parent := AParent;
  FNames := TStringList.Create;
  FNames.Sorted := True;
  FNames.Duplicates := dupIgnore;
  FNames.CaseSensitive := True;
  FPyNames := TStringList.Create;
end;

destructor TScope.Destroy;
begin
  FNames.Free;
  FPyNames.Free;
  inherited;
end;

function TScope.InMacro: Boolean;
var
  S: TScope;
begin
  S := Self;
  while S <> nil do
  begin
    if S.IsMacro then
      Exit(True);
    S := S.Parent;
  end;
  Result := False;
end;

function TScope.PyName(const Name: string): string;
var
  S: TScope;
  i: Integer;
begin
  S := Self;
  while S <> nil do
  begin
    if S.FNames.IndexOf(Name) >= 0 then
    begin
      i := S.FPyNames.IndexOfName(Name);
      if i >= 0 then
        Exit(S.FPyNames.ValueFromIndex[i]);
      Exit(Name);
    end;
    S := S.Parent;
  end;
  Result := Name;
end;

function TScope.Bind(const Name: string): string;
var
  S, Func, Root: TScope;
begin
  (* the scopes of the Python function this one is in *)
  Func := Self;
  while (Func.Parent <> nil) and not Func.IsFunc do
    Func := Func.Parent;
  S := Self;
  while S <> Func.Parent do
  begin
    if S.FNames.IndexOf(Name) >= 0 then
      Exit(S.PyName(Name)); (* assigned before in this function *)
    S := S.Parent;
  end;
  if Func.IsFunc and (Func.Parent <> nil) and Func.Parent.IsLocal(Name) then
  begin
    Root := Self;
    while Root.Parent <> nil do
      Root := Root.Parent;
    Inc(Root.FRenamed);
    Result := '_' + Name + '_' + IntToStr(Root.FRenamed);
    FNames.Add(Name);
    FPyNames.Add(Name + '=' + Result);
    Exit;
  end;
  FNames.Add(Name);
  Result := Name;
end;

procedure TScope.Add(const Name: string);
begin
  FNames.Add(Name);
end;

function TScope.IsLocal(const Name: string): Boolean;
var
  S: TScope;
begin
  S := Self;
  while S <> nil do
  begin
    if S.FNames.IndexOf(Name) >= 0 then
      Exit(True);
    S := S.Parent;
  end;
  Result := False;
end;

function TScope.LoopScope: TScope;
begin
  Result := Self;
  while (Result <> nil) and (Result.LoopVar = '') do
    Result := Result.Parent;
end;

(* TExpr *)

procedure TExpr.Add(E: TExpr);
begin
  SetLength(Items, Length(Items) + 1);
  Items[High(Items)] := E;
end;

(* TExprTranslator: tokens *)

constructor TExprTranslator.Create(const AFile, AFileSrc, ASrc: string; ABase: Integer;
  AScope: TScope);
begin
  FFile := AFile;
  FFileSrc := AFileSrc;
  FSrc := ASrc;
  FBase := ABase;
  FScope := AScope;
  FNodes := TList.Create;
  FPos := 1;
  Next;
end;

destructor TExprTranslator.Destroy;
var
  i: Integer;
begin
  for i := 0 to FNodes.Count - 1 do
    TExpr(FNodes[i]).Free;
  FNodes.Free;
  inherited;
end;

function TExprTranslator.Node(AKind: TExprKind; APos: Integer; const AValue: string): TExpr;
begin
  Result := TExpr.Create;
  Result.Kind := AKind;
  Result.Pos := APos;
  Result.Value := AValue;
  FNodes.Add(Result);
end;

procedure TExprTranslator.Fail(TokPos: Integer; const Msg: string);
begin
  CompileError(FFile, FFileSrc, FBase + TokPos - 1, Msg);
end;

procedure TExprTranslator.Next;
var
  L, Start: Integer;
  C, Quote: Char;
  Two: string;
begin
  L := Length(FSrc);
  while (FPos <= L) and (FSrc[FPos] in WhitespaceChars) do
    Inc(FPos);
  FTokPos := FPos;
  if FPos > L then
  begin
    FTokKind := xkEOF;
    FTokVal := '';
    Exit;
  end;
  C := FSrc[FPos];
  if C in NameStartChars then
  begin
    Start := FPos;
    while (FPos <= L) and (FSrc[FPos] in NameChars) do
      Inc(FPos);
    FTokKind := xkName;
    FTokVal := Copy(FSrc, Start, FPos - Start);
    Exit;
  end;
  if C in DigitChars then
  begin
    Start := FPos;
    FTokKind := xkInt;
    if (C = '0') and (FPos < L) and (FSrc[FPos + 1] in ['x', 'X', 'b', 'B', 'o', 'O']) then
    begin
      Inc(FPos, 2);
      while (FPos <= L) and (FSrc[FPos] in ['0'..'9', 'a'..'f', 'A'..'F', '_']) do
        Inc(FPos);
    end
    else
    begin
      while (FPos <= L) and (FSrc[FPos] in ['0'..'9', '_']) do
        Inc(FPos);
      if (FPos < L) and (FSrc[FPos] = '.') and (FSrc[FPos + 1] in DigitChars) then
      begin
        FTokKind := xkFloat;
        Inc(FPos);
        while (FPos <= L) and (FSrc[FPos] in ['0'..'9', '_']) do
          Inc(FPos);
      end;
      if (FPos <= L) and (FSrc[FPos] in ['e', 'E']) then
      begin
        FTokKind := xkFloat;
        Inc(FPos);
        if (FPos <= L) and (FSrc[FPos] in ['+', '-']) then
          Inc(FPos);
        while (FPos <= L) and (FSrc[FPos] in DigitChars) do
          Inc(FPos);
      end;
    end;
    FTokVal := Copy(FSrc, Start, FPos - Start);
    Exit;
  end;
  if C in ['"', ''''] then
  begin
    Quote := C;
    Start := FPos;
    Inc(FPos);
    while (FPos <= L) and (FSrc[FPos] <> Quote) do
    begin
      if FSrc[FPos] = '\' then
        Inc(FPos);
      Inc(FPos);
    end;
    if FPos > L then
      Fail(Start, 'Unclosed string');
    Inc(FPos);
    FTokKind := xkStr;
    FTokVal := Copy(FSrc, Start, FPos - Start);
    Exit;
  end;
  FTokKind := xkOp;
  Two := Copy(FSrc, FPos, 2);
  if InList(Two, ['**', '//', '==', '!=', '<=', '>=']) then
  begin
    FTokVal := Two;
    Inc(FPos, 2);
    Exit;
  end;
  if C in ['+', '-', '*', '/', '%', '~', '<', '>', '(', ')', '[', ']', '{', '}',
    ',', ':', '|', '.', '=', ';'] then
  begin
    FTokVal := C;
    Inc(FPos);
    Exit;
  end;
  Fail(FPos, 'Unexpected character `' + C + '`');
end;

function TExprTranslator.IsName(const V: string): Boolean;
begin
  Result := (FTokKind = xkName) and (FTokVal = V);
end;

function TExprTranslator.IsOp(const V: string): Boolean;
begin
  Result := (FTokKind = xkOp) and (FTokVal = V);
end;

procedure TExprTranslator.Expect(const V: string);
begin
  if not (IsOp(V) or IsName(V)) then
  begin
    if FTokKind = xkEOF then
      Fail(FTokPos, 'Expected `' + V + '` but the expression ended')
    else
      Fail(FTokPos, 'Expected `' + V + '` but found `' + FTokVal + '`');
  end;
  Next;
end;

(* True at the end of the source; fails on anything else. *)
function TExprTranslator.ParseEnd(const Where: string): Boolean;
begin
  if FTokKind <> xkEOF then
    Fail(FTokPos, 'Unexpected `' + FTokVal + '`' + Where);
  Result := True;
end;

(* TExprTranslator: parser *)

function TExprTranslator.ParseExpression: TExpr;
var
  Cond: TExpr;
begin
  Result := ParseOr;
  while IsName('if') do
  begin
    Cond := Node(ekCond, FTokPos);
    Next;
    Cond.Add(Result);
    Cond.Add(ParseOr);
    if IsName('else') then
    begin
      Next;
      Cond.Add(ParseExpression()); (* `()`: a call, not the Result *)
    end
    else
      Cond.Add(nil);
    Result := Cond;
  end;
end;

function TExprTranslator.ParseOr: TExpr;
var
  E: TExpr;
begin
  Result := ParseAnd;
  while IsName('or') do
  begin
    E := Node(ekBinary, FTokPos, 'or');
    Next;
    E.Add(Result);
    E.Add(ParseAnd);
    Result := E;
  end;
end;

function TExprTranslator.ParseAnd: TExpr;
var
  E: TExpr;
begin
  Result := ParseNot;
  while IsName('and') do
  begin
    E := Node(ekBinary, FTokPos, 'and');
    Next;
    E.Add(Result);
    E.Add(ParseNot);
    Result := E;
  end;
end;

function TExprTranslator.ParseNot: TExpr;
begin
  if IsName('not') then
  begin
    Result := Node(ekNot, FTokPos);
    Next;
    Result.Add(ParseNot()); (* `()`: a call, not the Result *)
  end
  else
    Result := ParseCompare;
end;

function TExprTranslator.ParseCompare: TExpr;
var
  First: TExpr;
  Op: string;
begin
  First := ParseMath1;
  Result := First;
  while True do
  begin
    if (FTokKind = xkOp) and InList(FTokVal, ['==', '!=', '<', '>', '<=', '>=']) then
    begin
      Op := FTokVal;
      Next;
    end
    else if IsName('in') then
    begin
      Op := 'in';
      Next;
    end
    else if IsName('not') then
    begin
      Next;
      if not IsName('in') then
        Fail(FTokPos, 'Expected `in` after `not`');
      Next;
      Op := 'not in';
    end
    else
      Break;
    if Result = First then
    begin
      Result := Node(ekCompare, First.Pos);
      Result.Add(First);
    end;
    SetLength(Result.Ops, Length(Result.Ops) + 1);
    Result.Ops[High(Result.Ops)] := Op;
    Result.Add(ParseMath1);
  end;
end;

function TExprTranslator.ParseMath1: TExpr;
var
  E: TExpr;
begin
  Result := ParseConcat;
  while (FTokKind = xkOp) and ((FTokVal = '+') or (FTokVal = '-')) do
  begin
    E := Node(ekBinary, FTokPos, FTokVal);
    Next;
    E.Add(Result);
    E.Add(ParseConcat);
    Result := E;
  end;
end;

function TExprTranslator.ParseConcat: TExpr;
var
  First: TExpr;
begin
  First := ParseMath2;
  Result := First;
  while IsOp('~') do
  begin
    if Result = First then
    begin
      Result := Node(ekConcat, First.Pos);
      Result.Add(First);
    end;
    Next;
    Result.Add(ParseMath2);
  end;
end;

function TExprTranslator.ParseMath2: TExpr;
var
  E: TExpr;
begin
  Result := ParsePow;
  while (FTokKind = xkOp) and InList(FTokVal, ['*', '/', '//', '%']) do
  begin
    E := Node(ekBinary, FTokPos, FTokVal);
    Next;
    E.Add(Result);
    E.Add(ParsePow);
    Result := E;
  end;
end;

function TExprTranslator.ParsePow: TExpr;
var
  E: TExpr;
begin
  Result := ParseUnary;
  (* Jinja's ** is left associative, Python's is right; the tree keeps
     Jinja's, and the generator parenthesises every operation *)
  while IsOp('**') do
  begin
    E := Node(ekBinary, FTokPos, '**');
    Next;
    E.Add(Result);
    E.Add(ParseUnary);
    Result := E;
  end;
end;

function TExprTranslator.ParseUnary(WithFilter: Boolean): TExpr;
begin
  if IsOp('-') or IsOp('+') then
  begin
    (* `-x|abs` is `(-x)|abs`, as in Jinja *)
    Result := Node(ekUnary, FTokPos, FTokVal);
    Next;
    Result.Add(ParseUnary(False));
  end
  else
    Result := ParsePostfix(ParsePrimary);
  if WithFilter then
    Result := ParseFilterExpr(Result);
end;

function TExprTranslator.ParsePrimary: TExpr;
var
  P: Integer;
begin
  P := FTokPos;
  case FTokKind of
    xkName:
      begin
        case FTokVal of
          'true', 'True': Result := Node(ekConst, P, 'True');
          'false', 'False': Result := Node(ekConst, P, 'False');
          'none', 'None': Result := Node(ekConst, P, 'None');
        else
          Result := Node(ekName, P, FTokVal);
        end;
        Next;
      end;
    xkStr:
      begin
        Result := Node(ekStr, P, FTokVal);
        Next;
        (* adjacent literals concatenate, in Jinja and in Python *)
        while FTokKind = xkStr do
        begin
          Result.Value := Result.Value + ' ' + FTokVal;
          Next;
        end;
      end;
    xkInt, xkFloat:
      begin
        Result := Node(ekConst, P, FTokVal);
        Next;
      end;
    xkOp:
      begin
        if FTokVal = '(' then
        begin
          Next;
          Result := Node(ekTuple, P);
          (* one item without a trailing comma is just parentheses *)
          if not ParseSequence(Result, ')') and (Length(Result.Items) = 1) then
            Result := Result.Items[0];
        end
        else if FTokVal = '[' then
        begin
          Next;
          Result := Node(ekList, P);
          ParseSequence(Result, ']');
        end
        else if FTokVal = '{' then
        begin
          Next;
          Result := Node(ekDict, P);
          while not IsOp('}') do
          begin
            Result.Add(ParseExpression);
            Expect(':');
            Result.Add(ParseExpression);
            if IsOp(',') then
              Next
            else
              Break;
          end;
          Expect('}');
        end
        else
          Fail(P, 'Unexpected `' + FTokVal + '`');
      end;
  else
    Fail(P, 'Unexpected end of expression');
  end;
end;

(* Comma-separated items up to Close, which is consumed. Returns whether
   the last item was followed by a comma (it makes `(x,)` a tuple). *)
function TExprTranslator.ParseSequence(E: TExpr; const Close: string): Boolean;
begin
  Result := False;
  while not IsOp(Close) do
  begin
    E.Add(ParseExpression);
    Result := IsOp(',');
    if Result then
      Next
    else
      Break;
  end;
  Expect(Close);
  E.Flag := Result;
end;

(* `(args)` at the current position, into E.Args. False if there is none. *)
function TExprTranslator.ParseCallArgs(E: TExpr): Boolean;
var
  A: TCallArg;
  SavePos, SaveTokPos: Integer;
  SaveKind: TXTokKind;
  SaveVal: string;
begin
  if not IsOp('(') then
    Exit(False);
  Next;
  while not IsOp(')') do
  begin
    A := Default(TCallArg);
    A.Kind := akPositional;
    if FTokKind = xkName then
    begin
      (* look ahead for `name=` (but not `name==`) *)
      SavePos := FPos;
      SaveKind := FTokKind;
      SaveVal := FTokVal;
      SaveTokPos := FTokPos;
      Next;
      if IsOp('=') then
      begin
        Next;
        A.Kind := akKeyword;
        A.Name := SaveVal;
      end
      else
      begin
        FPos := SavePos;
        FTokKind := SaveKind;
        FTokVal := SaveVal;
        FTokPos := SaveTokPos;
      end;
    end;
    if A.Kind = akPositional then
      if IsOp('**') then
      begin
        Next;
        A.Kind := akDoubleStar;
      end
      else if IsOp('*') then
      begin
        Next;
        A.Kind := akStar;
      end;
    A.Value := ParseExpression;
    SetLength(E.Args, Length(E.Args) + 1);
    E.Args[High(E.Args)] := A;
    if IsOp(',') then
      Next
    else
      Break;
  end;
  Expect(')');
  Result := True;
end;

function TExprTranslator.ParsePostfix(E: TExpr): TExpr;
var
  N: TExpr;
  P: Integer;
begin
  Result := E;
  while True do
  begin
    P := FTokPos;
    if IsOp('.') then
    begin
      Next;
      if not (FTokKind in [xkName, xkInt]) then
        Fail(FTokPos, 'Expected an attribute name after `.`');
      N := Node(ekGetAttr, P, FTokVal);
      N.Flag := FTokKind = xkInt;
      Next;
      N.Add(Result);
      Result := N;
    end
    else if IsOp('[') then
    begin
      Next;
      N := Node(ekGetItem, P);
      N.Add(Result);
      if not IsOp(':') then
        N.Add(ParseExpression)
      else
        N.Add(nil);
      if IsOp(':') then
      begin
        (* a slice: [start:stop] or [start:stop:step] *)
        N.Kind := ekSlice;
        Next;
        if not (IsOp(':') or IsOp(']')) then
          N.Add(ParseExpression)
        else
          N.Add(nil);
        if IsOp(':') then
        begin
          N.Flag := True;
          Next;
          if not IsOp(']') then
            N.Add(ParseExpression)
          else
            N.Add(nil);
        end;
      end;
      Expect(']');
      Result := N;
    end
    else if IsOp('(') then
    begin
      N := Node(ekCall, P);
      N.Add(Result);
      ParseCallArgs(N);
      Result := N;
    end
    else
      Break;
  end;
end;

(* `name[.name...][(args)]` after a `|`, applied to Subject. *)
function TExprTranslator.ParseFilter(Subject: TExpr): TExpr;
begin
  if FTokKind <> xkName then
    Fail(FTokPos, 'Expected a filter name after `|`');
  Result := Node(ekFilter, FTokPos, FTokVal);
  Next;
  while IsOp('.') do
  begin
    Next;
    Result.Value := Result.Value + '.' + FTokVal;
    Next;
  end;
  Result.Add(Subject);
  Result.HasArgs := ParseCallArgs(Result);
end;

function TExprTranslator.ParseFilterExpr(E: TExpr): TExpr;
var
  T: TExpr;
  A: TCallArg;
begin
  Result := E;
  while True do
  begin
    if IsOp('|') then
    begin
      Next;
      Result := ParseFilter(Result);
    end
    else if IsName('is') then
    begin
      T := Node(ekTest, FTokPos);
      Next;
      if IsName('not') then
      begin
        T.Flag := True;
        Next;
      end;
      if FTokKind <> xkName then
        Fail(FTokPos, 'Expected a test name after `is`');
      T.Value := FTokVal;
      Next;
      T.Add(Result);
      (* the argument: `(a, b)`, or a single primary as in `is divisibleby 3` *)
      T.HasArgs := ParseCallArgs(T);
      if not T.HasArgs and
        ((FTokKind in [xkName, xkStr, xkInt, xkFloat]) or IsOp('[') or IsOp('{') or IsOp('('))
        and not (IsName('else') or IsName('or') or IsName('and') or IsName('if')) then
      begin
        if IsName('is') then
          Fail(FTokPos, 'You cannot chain multiple tests with one `is`');
        A := Default(TCallArg);
        A.Kind := akPositional;
        A.Value := ParsePostfix(ParsePrimary);
        SetLength(T.Args, 1);
        T.Args[0] := A;
        T.HasArgs := True;
      end;
      Result := T;
    end
    else
      Break;
  end;
end;

(* TExprTranslator: generator *)

(* `attrs` and `loop` are minijx's own objects: `attrs.render` needs no
   getattr/getitem fallback *)
function TExprTranslator.IsRuntimeObject(E: TExpr): Boolean;
begin
  Result := (E.Kind = ekName) and
    ((E.Value = 'loop') or ((E.Value = 'attrs') and FScope.IsLocal('attrs')));
end;

function TExprTranslator.IsGlobal(E: TExpr): Boolean;
begin
  Result := (E.Kind = ekName) and (E.Value <> 'loop') and not FScope.IsLocal(E.Value)
    and not InList(E.Value, PyBuiltins);
end;

function TExprTranslator.GenName(E: TExpr): string;
var
  S: TScope;
begin
  if E.Value = 'loop' then
  begin
    S := FScope.LoopScope;
    if S = nil then
      Fail(E.Pos, '`loop` used outside of a for loop');
    S.LoopUsed := True;
    UsesLoop := True;
    Exit(S.LoopVar);
  end;
  if InList(E.Value, ['caller', 'varargs', 'kwargs']) and FScope.InMacro
    and not FScope.IsLocal(E.Value) then
    Fail(E.Pos, '`' + E.Value + '` is not supported in minijx macros');
  if IsGlobal(E) then
    Result := '_globals[' + PyStr(E.Value) + ']'
  else
    Result := FScope.PyName(E.Value);
end;

(* The arguments of a call as Python. Keyword arguments named like a Python
   keyword (`class=`) travel in a `**{...}`. *)
function TExprTranslator.GenArgs(E: TExpr): string;
var
  i: Integer;
  A: TCallArg;
  Kw: string;
begin
  Result := '';
  Kw := '';
  for i := 0 to High(E.Args) do
  begin
    A := E.Args[i];
    case A.Kind of
      akPositional: Result := Result + Gen(A.Value) + ', ';
      akStar: Result := Result + '*' + Gen(A.Value) + ', ';
      akDoubleStar: Result := Result + '**' + Gen(A.Value) + ', ';
      akKeyword:
        if IsPyKeyword(A.Name) then
          Kw := Kw + PyStr(A.Name) + ': ' + Gen(A.Value) + ', '
        else
          Result := Result + A.Name + '=' + Gen(A.Value) + ', ';
    end;
  end;
  if Kw <> '' then
    Result := Result + '**{' + Copy(Kw, 1, Length(Kw) - 2) + '}, ';
  if Result <> '' then
    SetLength(Result, Length(Result) - 2);
end;

(* A missing global, attribute or item gives UNDEFINED instead of raising;
   for `x | default(...)`. *)
function TExprTranslator.GenSafe(E: TExpr): string;
begin
  if IsGlobal(E) then
    Result := '_globals.get(' + PyStr(E.Value) + ', UNDEFINED)'
  else if E.Kind = ekGetAttr then
  begin
    if E.Flag then
      Result := 'getattr_(' + Gen(E.Items[0]) + ', ' + E.Value + ', UNDEFINED)'
    else
      Result := 'getattr_(' + Gen(E.Items[0]) + ', ' + PyStr(E.Value) + ', UNDEFINED)';
  end
  else if E.Kind = ekGetItem then
    Result := 'getitem(' + Gen(E.Items[0]) + ', ' + Gen(E.Items[1]) + ', UNDEFINED)'
  else
    Result := Gen(E);
end;

(* `x is defined`, without raising for a missing x. *)
function TExprTranslator.GenDefined(E: TExpr): string;
begin
  if E.Kind = ekName then
  begin
    if IsGlobal(E) then
      Result := '(' + PyStr(E.Value) + ' in _globals)'
    else
    begin
      GenName(E); (* `loop` outside a loop is still an error *)
      Result := 'True';
    end;
  end
  else if E.Kind = ekGetAttr then
  begin
    if E.Flag then
      Result := 'has_attr(' + Gen(E.Items[0]) + ', ' + E.Value + ')'
    else
      Result := 'has_attr(' + Gen(E.Items[0]) + ', ' + PyStr(E.Value) + ')';
  end
  else if E.Kind = ekGetItem then
    Result := 'has_attr(' + Gen(E.Items[0]) + ', ' + Gen(E.Items[1]) + ')'
  else
    Result := '(' + Gen(E) + ' is not None)';
end;

(* Filters and tests are looked up by name, in the dict the catalog passes in
   `_globals` (bound to `_f` / `_t` at the top of the component), so custom
   ones work and can replace builtin filters. *)
function TExprTranslator.FilterCall(const Name, Subject, Args: string): string;
begin
  UsesFilters := True;
  Result := '_f[' + PyStr(Name) + '](' + Subject;
  if Args <> '' then
    Result := Result + ', ' + Args;
  Result := Result + ')';
end;

function TExprTranslator.GenTest(E: TExpr): string;
var
  Subject, Arg: string;
  Negate: Boolean;
begin
  Negate := E.Flag;
  (* tests with a Python equivalent are compiled into it *)
  if (E.Value = 'defined') or (E.Value = 'undefined') then
  begin
    Result := GenDefined(E.Items[0]);
    if E.Value = 'undefined' then
      Negate := not Negate;
  end
  else
  begin
    Subject := Gen(E.Items[0]);
    Arg := GenArgs(E);
    case E.Value of
      'none': Result := '(' + Subject + ' is None)';
      'in': Result := '(' + Subject + ' in ' + Arg + ')';
      'callable': Result := 'callable(' + Subject + ')';
      'sameas': Result := '(' + Subject + ' is ' + Arg + ')';
      'eq', 'equalto', '==': Result := '(' + Subject + ' == ' + Arg + ')';
      'ne', '!=': Result := '(' + Subject + ' != ' + Arg + ')';
      'gt', 'greaterthan', '>': Result := '(' + Subject + ' > ' + Arg + ')';
      'ge', '>=': Result := '(' + Subject + ' >= ' + Arg + ')';
      'lt', 'lessthan', '<': Result := '(' + Subject + ' < ' + Arg + ')';
      'le', '<=': Result := '(' + Subject + ' <= ' + Arg + ')';
    else
      UsesTests := True;
      Result := '_t[' + PyStr(E.Value) + '](' + Subject;
      if Arg <> '' then
        Result := Result + ', ' + Arg;
      Result := Result + ')';
    end;
  end;
  if Negate then
    Result := '(not ' + Result + ')';
end;

function TExprTranslator.Gen(E: TExpr): string;
var
  i: Integer;
  Subject: string;
begin
  case E.Kind of
    ekName: Result := GenName(E);
    ekConst, ekStr: Result := E.Value;
    ekList, ekTuple, ekDict, ekConcat:
      begin
        Result := '';
        i := 0;
        while i <= High(E.Items) do
        begin
          if i > 0 then
            Result := Result + ', ';
          Result := Result + Gen(E.Items[i]);
          if E.Kind = ekDict then
          begin
            Result := Result + ': ' + Gen(E.Items[i + 1]);
            Inc(i);
          end;
          Inc(i);
        end;
        case E.Kind of
          ekList: Result := '[' + Result + ']';
          ekDict: Result := '{' + Result + '}';
          ekConcat:
            if Autoescape then
              Result := 'mconcat(' + Result + ')'
            else
              Result := 'concat(' + Result + ')';
        else
          if Length(E.Items) = 1 then
            Result := '(' + Result + ',)'
          else
            Result := '(' + Result + ')';
        end;
      end;
    ekGetAttr:
      if IsRuntimeObject(E.Items[0]) and not E.Flag then
        Result := Gen(E.Items[0]) + '.' + E.Value
      else if E.Flag then
        Result := 'getattr_(' + Gen(E.Items[0]) + ', ' + E.Value + ')'
      else
        Result := 'getattr_(' + Gen(E.Items[0]) + ', ' + PyStr(E.Value) + ')';
    ekGetItem:
      Result := 'getitem(' + Gen(E.Items[0]) + ', ' + Gen(E.Items[1]) + ')';
    ekSlice:
      begin
        Result := Gen(E.Items[0]) + '[';
        for i := 1 to High(E.Items) do
        begin
          if i > 1 then
            Result := Result + ':';
          if E.Items[i] <> nil then
            Result := Result + Gen(E.Items[i]);
        end;
        Result := Result + ']';
      end;
    ekCall: Result := Gen(E.Items[0]) + '(' + GenArgs(E) + ')';
    ekFilter:
      begin
        if (E.Value = 'default') or (E.Value = 'd') then
          Subject := GenSafe(E.Items[0])
        else
          Subject := Gen(E.Items[0]);
        Result := FilterCall(E.Value, Subject, GenArgs(E));
      end;
    ekTest: Result := GenTest(E);
    ekUnary: Result := '(' + E.Value + Gen(E.Items[0]) + ')';
    ekNot: Result := '(not ' + Gen(E.Items[0]) + ')';
    ekBinary: Result := '(' + Gen(E.Items[0]) + ' ' + E.Value + ' ' + Gen(E.Items[1]) + ')';
    ekCompare:
      begin
        Result := '(' + Gen(E.Items[0]);
        for i := 0 to High(E.Ops) do
          Result := Result + ' ' + E.Ops[i] + ' ' + Gen(E.Items[i + 1]);
        Result := Result + ')';
      end;
    ekCond:
      begin
        Result := '(' + Gen(E.Items[0]) + ' if ' + Gen(E.Items[1]) + ' else ';
        if E.Items[2] <> nil then
          Result := Result + Gen(E.Items[2])
        else
          Result := Result + '""'; (* Jinja renders a missing else as an empty string *)
        Result := Result + ')';
      end;
  end;
end;

(* TExprTranslator: entry points *)

function TExprTranslator.Translate: string;
var
  E: TExpr;
begin
  E := ParseExpression;
  ParseEnd('');
  Result := Gen(E);
end;

function TExprTranslator.TranslateOutput(out Safe: Boolean): string;
var
  E: TExpr;
begin
  E := ParseExpression;
  ParseEnd('');
  Safe := (E.Kind = ekConst) or
    ((E.Kind = ekFilter) and InList(E.Value, ['e', 'escape', 'forceescape', 'safe']));
  Result := Gen(E);
end;

function TExprTranslator.TranslateTarget(out Names: TStringArray): string;
var
  N: Integer;
  Paren: Boolean;

  procedure AddName;
  begin
    if FTokKind <> xkName then
      Fail(FTokPos, 'Expected a variable name');
    if InList(FTokVal, ['in', 'if', 'and', 'or', 'not', 'is']) then
      Fail(FTokPos, '`' + FTokVal + '` cannot be a variable name');
    SetLength(Names, N + 1);
    Names[N] := FTokVal;
    Inc(N);
    Next;
  end;

begin
  N := 0;
  SetLength(Names, 0);
  Paren := IsOp('(');
  if Paren then
    Next;
  AddName;
  while IsOp(',') do
  begin
    Next;
    if IsOp(')') or IsName('in') then
      Break;
    AddName;
  end;
  if Paren then
    Expect(')');
  if N = 1 then
    Result := Names[0]
  else
  begin
    Result := '(';
    for N := 0 to High(Names) do
    begin
      if N > 0 then
        Result := Result + ', ';
      Result := Result + Names[N];
    end;
    Result := Result + ')';
  end;
end;

procedure TExprTranslator.TranslateFor(out Target: string; out Names: TStringArray;
  out Iter: string; out Cond: string; out Recursive: Boolean;
  IterScope, BodyScope: TScope);
var
  IterExpr, CondExpr: TExpr;
  i: Integer;
begin
  TranslateTarget(Names);
  if not IsName('in') then
    Fail(FTokPos, 'Expected `in`');
  Next;
  IterExpr := ParseOr; (* no inline-if here, like Jinja *)
  CondExpr := nil;
  if IsName('if') then
  begin
    Next;
    CondExpr := ParseExpression;
  end;
  Recursive := IsName('recursive');
  if Recursive then
    Next;
  ParseEnd(' in for statement');

  (* the iterable is resolved in the enclosing scope *)
  FScope := IterScope;
  Iter := Gen(IterExpr);

  (* the target, in the body's scope: a recursive loop's body is a function *)
  BodyScope.IsFunc := Recursive;
  if Length(Names) = 1 then
    Target := BodyScope.Bind(Names[0])
  else
  begin
    Target := '(';
    for i := 0 to High(Names) do
    begin
      if i > 0 then
        Target := Target + ', ';
      Target := Target + BodyScope.Bind(Names[i]);
    end;
    Target := Target + ')';
  end;

  (* the condition, where the loop variables are bound *)
  Cond := '';
  if CondExpr <> nil then
  begin
    FScope := BodyScope;
    try
      Cond := Gen(CondExpr);
    finally
      FScope := IterScope;
    end;
  end;
end;

procedure TExprTranslator.TranslateSet(out Name: string; out Value: string);
var
  E: TExpr;
begin
  if FTokKind <> xkName then
    Fail(FTokPos, 'Expected a variable name after `set`');
  Name := FTokVal;
  Next;
  if IsOp(',') or IsOp('.') or IsOp('[') then
    Fail(FTokPos, 'minijx only supports `{% set name = value %}`');
  Expect('=');
  E := ParseExpression;
  ParseEnd(' in set statement');
  Value := Gen(E);
end;

(* `upper|replace("a", "b")` applied to Subject (a Python expression). *)
function TExprTranslator.TranslateFilterChain(const Subject: string): string;
var
  Chain: array of TExpr;
  F: TExpr;
  i: Integer;
begin
  SetLength(Chain, 0);
  while True do
  begin
    if FTokKind <> xkName then
      Fail(FTokPos, 'Expected a filter name');
    F := ParseFilter(nil);
    SetLength(Chain, Length(Chain) + 1);
    Chain[High(Chain)] := F;
    if IsOp('|') then
      Next
    else
      Break;
  end;
  ParseEnd(' in filter statement');
  Result := Subject;
  for i := 0 to High(Chain) do
    Result := FilterCall(Chain[i].Value, Result, GenArgs(Chain[i]));
end;

(* `(a, b=1)` -> `a, b=1`; `()` -> ''. The generator wraps the arguments
   written without parentheses (`{% cache a, b=1 %}`) in them. *)
function TExprTranslator.TranslateTagArgs: string;
var
  E: TExpr;
begin
  E := Node(ekCall, FTokPos);
  if not ParseCallArgs(E) then
    Fail(FTokPos, 'Expected `(`');
  ParseEnd(' in the arguments of the tag');
  Result := GenArgs(E);
end;

procedure TExprTranslator.TranslateMacroSig(MacroScope: TScope; out Name: string;
  out Params, Defaults: TStringArray);
var
  E: TExpr;
  A: TCallArg;
  i, j: Integer;
  SeenDefault: Boolean;
  Outer: TScope;
begin
  if FTokKind <> xkName then
    Fail(FTokPos, 'Expected the name of the macro');
  Name := FTokVal;
  if IsPyKeyword(Name) then
    Fail(FTokPos, '`' + Name + '` cannot be the name of a macro');
  Next;
  E := Node(ekCall, FTokPos);
  if not ParseCallArgs(E) then
    Fail(FTokPos, 'Expected `(` after the name of the macro');
  ParseEnd(' in macro statement');

  SetLength(Params, Length(E.Args));
  SetLength(Defaults, Length(E.Args));
  SeenDefault := False;
  for i := 0 to High(E.Args) do
  begin
    A := E.Args[i];
    case A.Kind of
      akPositional:
        begin
          if A.Value.Kind <> ekName then
            Fail(A.Value.Pos, 'A macro parameter is a name, or `name=default`');
          if SeenDefault then
            Fail(A.Value.Pos, 'A parameter without a default cannot follow one with a default');
          Params[i] := A.Value.Value;
          Defaults[i] := '';
        end;
      akKeyword:
        begin
          SeenDefault := True;
          Params[i] := A.Name;
        end;
    else
      Fail(A.Value.Pos, 'minijx macros do not take `*args` or `**kwargs`');
    end;
    if IsPyKeyword(Params[i]) then
      Fail(A.Value.Pos, '`' + Params[i] + '` cannot be the name of a parameter');
    for j := 0 to i - 1 do
      if Params[j] = Params[i] then
        Fail(A.Value.Pos, 'Duplicate parameter `' + Params[i] + '`');
  end;
  for i := 0 to High(Params) do
    MacroScope.Add(Params[i]);

  Outer := FScope;
  FScope := MacroScope;
  try
    for i := 0 to High(E.Args) do
      if E.Args[i].Kind = akKeyword then
        Defaults[i] := Gen(E.Args[i].Value);
  finally
    FScope := Outer;
  end;
end;

function TExprTranslator.LiteralType: string;
var
  E: TExpr;

  function NumberType(const V: string): string;
  begin
    if (Pos('.', V) > 0) or (Pos('e', V) > 0) or (Pos('E', V) > 0) then
      Result := 'float'
    else
      Result := 'int';
  end;

begin
  E := ParseExpression;
  ParseEnd('');
  Result := '';
  case E.Kind of
    ekStr: Result := 'str';
    ekList: Result := 'list';
    ekDict: Result := 'dict';
    ekTuple: Result := 'tuple';
    ekConst:
      if (E.Value = 'True') or (E.Value = 'False') then
        Result := 'bool'
      else if E.Value = 'None' then
        Result := 'NoneType'
      else if (E.Value <> '') and (E.Value[1] in ['0'..'9', '.']) then
        Result := NumberType(E.Value);
    ekUnary:
      if (E.Items[0].Kind = ekConst) and (E.Items[0].Value <> '') and
        (E.Items[0].Value[1] in ['0'..'9', '.']) then
        Result := NumberType(E.Items[0].Value);
  end;
end;

end.
