(* minijx: the arguments declared in `{# def ... #}`.

  As in Jx, the declaration is a Python argument list: names, optional
  annotations and defaults. A default is a Python expression (not a Jinja
  one) that may only use literals and the names Jx allows. *)
unit mjdefs;

{$mode objfpc}{$H+}

interface

uses
  SysUtils, Classes, StrUtils, mjerrors, mjutil, mjparser, mjcomponent;

(* The arguments of Doc's `{# def #}`; none if it has no declaration. *)
function ParseDefArgs(Doc: TDocument): TArgArray;

(* A default value as Jx reads it: copied as is, with `true`/`false` (and
   `none`) turned into Python's. Only `len`, `max`, `min`, `pow`, `sum` and
   the names the expression binds itself (comprehension variables, lambda
   parameters) may be used; any other name, attribute names included, is an
   error, like Jx's "Use of ... not allowed". Base: offset of Src in the
   file, for error positions. *)
function PythonDefault(const FileName, FileSrc, Src: string; Base: Integer): string;

implementation

(* Index just past the string literal starting at I (0 if unclosed). *)
function SkipPyString(const Src: string; I: Integer): Integer;
var
  Quote: Char;
  L: Integer;
begin
  L := Length(Src);
  Quote := Src[I];
  if Copy(Src, I, 3) = StringOfChar(Quote, 3) then
  begin
    Result := PosEx(StringOfChar(Quote, 3), Src, I + 3);
    if Result > 0 then
      Inc(Result, 3);
    Exit;
  end;
  Inc(I);
  while (I <= L) and (Src[I] <> Quote) do
  begin
    if Src[I] = '\' then
      Inc(I);
    Inc(I);
  end;
  if I > L then
    Exit(0);
  Result := I + 1;
end;

(* Names the expression binds itself, which Jx accepts: comprehension
   variables (`for x, y in`) and lambda parameters (`lambda a, b:`). *)
procedure CollectBoundNames(const Src: string; Bound: TStringList);
var
  i, Start, L: Integer;
  Name: string;
  InFor, InLambda: Boolean;
begin
  L := Length(Src);
  InFor := False;
  InLambda := False;
  i := 1;
  while i <= L do
  begin
    if Src[i] in ['"', ''''] then
    begin
      i := SkipPyString(Src, i);
      if i = 0 then
        Exit;
      Continue;
    end;
    if InLambda and (Src[i] = ':') then
      InLambda := False;
    if Src[i] in NameStartChars then
    begin
      Start := i;
      while (i <= L) and (Src[i] in NameChars) do
        Inc(i);
      Name := Copy(Src, Start, i - Start);
      if Name = 'for' then
        InFor := True
      else if Name = 'lambda' then
        InLambda := True
      else if InFor and (Name = 'in') then
        InFor := False
      else if InFor or InLambda then
        Bound.Add(Name);
      Continue;
    end;
    Inc(i);
  end;
end;

function PythonDefault(const FileName, FileSrc, Src: string; Base: Integer): string;
var
  i, Start, L: Integer;
  Name: string;
  Bound: TStringList;
  Out: TBuf;
begin
  L := Length(Src);
  Bound := TStringList.Create;
  Out := TBuf.Create;
  try
    CollectBoundNames(Src, Bound);
    i := 1;
    while i <= L do
    begin
      if Src[i] in ['"', ''''] then
      begin
        (* a string literal, triple-quoted or not, copied untouched *)
        Start := i;
        i := SkipPyString(Src, i);
        if i = 0 then
          CompileError(FileName, FileSrc, Base + Start - 1, 'Unclosed string');
        Out.Add(Copy(Src, Start, i - Start));
      end
      else if Src[i] in NameStartChars then
      begin
        Start := i;
        while (i <= L) and (Src[i] in NameChars) do
          Inc(i);
        Name := Copy(Src, Start, i - Start);
        (* a string prefix (f"", r"", b"") belongs to the literal after it *)
        if (i <= L) and (Src[i] in ['"', '''']) and (Length(Name) <= 2) then
        begin
          Out.Add(Name);
          Continue;
        end;
        case Name of
          'true', 'True': Out.Add('True');
          'false', 'False': Out.Add('False');
          'none', 'None': Out.Add('None');
          'len', 'max', 'min', 'pow', 'sum',
          'if', 'else', 'and', 'or', 'not', 'in', 'is', 'for', 'lambda':
            Out.Add(Name);
        else
          if Bound.IndexOf(Name) < 0 then
            CompileError(FileName, FileSrc, Base + Start - 1,
              'Use of ' + Name + ' not allowed in the default value');
          Out.Add(Name);
        end;
      end
      else if Src[i] in DigitChars then
      begin
        (* numbers, including `1e5`, `0x1f`, `1_000`, `2j` *)
        Start := i;
        while (i <= L) and (Src[i] in NameChars + ['.']) do
        begin
          if (Src[i] in ['e', 'E']) and (i < L) and (Src[i + 1] in ['+', '-']) then
            Inc(i);
          Inc(i);
        end;
        Out.Add(Copy(Src, Start, i - Start));
      end
      else
      begin
        Out.Add(Src[i]);
        Inc(i);
      end;
    end;
    Result := Trim(Out.Join);
    if Result = '' then
      CompileError(FileName, FileSrc, Base, 'Missing default value');
  finally
    Out.Free;
    Bound.Free;
  end;
end;

(* One `name[: annotation][= default]`; PPos: its offset in the declaration. *)
function ParseArg(Doc: TDocument; const P: string; PPos: Integer; out A: TArg): Boolean;
var
  j, Depth, NameEnd, AnnStart: Integer;
  Quote: Char;

  procedure Fail(Offset: Integer; const Msg: string);
  begin
    CompileError(Doc.FileName, Doc.Source, Doc.DefPos + PPos - 1 + Offset - 1, Msg);
  end;

begin
  A := Default(TArg);
  j := 1;
  while (j <= Length(P)) and (P[j] in ['*', '/', ' ']) do
    Inc(j);
  if j > Length(P) then
    Exit(False);
  if not (P[j] in NameStartChars) then
    Fail(j, 'Invalid argument name in `{# def #}`');
  NameEnd := j;
  while (NameEnd <= Length(P)) and (P[NameEnd] in NameChars) do
    Inc(NameEnd);
  A.Name := Copy(P, j, NameEnd - j);
  j := NameEnd;
  while (j <= Length(P)) and (P[j] in WhitespaceChars) do
    Inc(j);
  if (j <= Length(P)) and (P[j] = ':') then
  begin
    (* the annotation runs up to a `=` outside brackets and strings *)
    AnnStart := j + 1;
    j := AnnStart;
    Depth := 0;
    Quote := #0;
    while j <= Length(P) do
    begin
      if Quote <> #0 then
      begin
        if P[j] = '\' then
          Inc(j)
        else if P[j] = Quote then
          Quote := #0;
      end
      else if P[j] in ['"', ''''] then
        Quote := P[j]
      else if P[j] in ['(', '[', '{'] then
        Inc(Depth)
      else if P[j] in [')', ']', '}'] then
        Dec(Depth)
      else if (P[j] = '=') and (Depth = 0) then
        Break;
      Inc(j);
    end;
    A.Annotation := Trim(Copy(P, AnnStart, j - AnnStart));
  end;
  if (j <= Length(P)) and (P[j] = '=') then
  begin
    A.HasDefault := True;
    A.Default := PythonDefault(Doc.FileName, Doc.Source, Copy(P, j + 1, Length(P)),
      Doc.DefPos + PPos - 1 + j);
  end
  else if j <= Length(P) then
    Fail(j, 'Unexpected `' + P[j] + '` in `{# def #}`');
  Result := True;
end;

function ParseDefArgs(Doc: TDocument): TArgArray;
var
  S, Part: string;
  i, Depth, Start, L: Integer;
  Quote: Char;
  A: TArg;

  procedure AddPart(From, Upto: Integer);
  begin
    Part := Trim(Copy(S, From, Upto - From));
    if (Part <> '') and ParseArg(Doc, Part, From, A) then
    begin
      SetLength(Result, Length(Result) + 1);
      Result[High(Result)] := A;
    end;
  end;

begin
  SetLength(Result, 0);
  if not Doc.HasDef then
    Exit;
  (* split at the commas outside brackets and strings *)
  S := Doc.DefExpr;
  L := Length(S);
  Depth := 0;
  Quote := #0;
  Start := 1;
  i := 1;
  while i <= L do
  begin
    if Quote <> #0 then
    begin
      if S[i] = '\' then
        Inc(i)
      else if S[i] = Quote then
        Quote := #0;
    end
    else if S[i] in ['"', ''''] then
      Quote := S[i]
    else if S[i] in ['(', '[', '{'] then
      Inc(Depth)
    else if S[i] in [')', ']', '}'] then
      Dec(Depth)
    else if (S[i] = ',') and (Depth = 0) then
    begin
      AddPart(Start, i);
      Start := i + 1;
    end;
    Inc(i);
  end;
  AddPart(Start, L + 1);
end;

end.
