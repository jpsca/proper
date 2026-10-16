(* jxc: from .jx files to Python modules.

  A TCompiler loads .jx files, resolves their `{# import #}` declarations
  against the root folders, and emits one Python module per file. Every
  component the file depends on (transitively) is copied into that module as
  a private function, so the module only imports the runtime (`proper.views`). *)
unit jxcompiler;

{$mode objfpc}{$H+}

interface

uses
  SysUtils, Classes, jxerrors, jxutil, jxparser, jxcomponent, jxdefs, jxgen;

type
  TCompiler = class
  private
    FRoots: TStringArray; (* absolute, with a trailing separator *)
    FCache: TStringList;  (* absolute path -> TComponent *)
    FNames: TStringList;  (* function names already given out *)
    FAutoescape: TStringList; (* extensions compiled with autoescape, sorted *)
    FTags: TStringList;       (* custom tag names, sorted *)
    FPure: TStringList;       (* globals whose calls are cached, sorted *)
    FOutput: string;          (* where the modules go; '' for next to each .jx *)
    FOutNames: TStringArray;  (* with FOutput: the subfolder of each root *)
    function IsAutoescaped(const Path: string): Boolean;
    function ResolveImport(C: TComponent; const D: TImportDecl; out RootIdx: Integer): string;
    function MangledName(const Path: string; RootIdx: Integer): string;
  public
    constructor Create(const ARoots, AAutoescape, ATags, APure: TStringArray;
      const AOutput: string = '');
    (* Where the module of a .jx found in the root RootIdx goes. *)
    function ModulePath(const JxPath: string; RootIdx: Integer): string;
    destructor Destroy; override;
    (* Load and resolve a component and everything it imports. *)
    function Load(const Path: string; RootIdx: Integer): TComponent;
    (* The full Python module for a component, to be written at OutPath. *)
    function CompileModule(C: TComponent; const OutPath: string): string;
  end;

const
  (* Version of the generated module layout; must match MODULE_FORMAT in
     src/proper/views/catalog.py. 3: CSS/JS are plain URLs (2 had pairs).
     4: `|default` receives UNDEFINED, not None, for a missing value.
     5: filters and tests are looked up in dicts (`_f["name"]`), which the
        catalog can replace with its own.
     6: autoescape; the module declares AUTOESCAPE and ESCAPED; custom tags,
        declared in TAGS.
     7: LINEMAP, where each line of the module comes from in the templates,
        and COMPONENTS, the function of each component.
     8: annotations are not evaluated (`from __future__ import annotations`),
        builtin types are checked, and defaults that are not literals are
        evaluated on each call.
     9: `attrs=` on a component call fills its declared arguments too, as Jx
        (`_merge_attrs`).
     10: the runtime is `proper.views`.
     11: PURE, the cache of their calls (`_P`), and functions that return
        their one piece of output, without a list.
     12: the format is VIEWS_FORMAT, and the keys in `_globals` `__views_*__`. *)
  ModuleFormat = 12;
  (* Taken from $JXC_VERSION when compiling, which Proper's
     `_native/build.py` sets. *)
  CompilerVersion = {$I %JXC_VERSION%};

(* `dir/sitemap.xml.jx` -> `dir/sitemap_xml.py`: the `.jx` is dropped and any
   other dot in the file name becomes `_`, so the module is importable. *)
function OutputPath(const JxPath: string): string;

(* The subfolder of the output folder for each root: its name, with `-2`,
   `-3`... when an earlier root has the same one. Must match
   `output_names` in src/proper/views/catalog.py. *)
function OutputNames(const Roots: TStringArray): TStringArray;

implementation

function OutputPath(const JxPath: string): string;
var
  Name: string;
begin
  Name := ExtractFileName(JxPath);
  if EndsWith(Name, '.jx') then
    Delete(Name, Length(Name) - 2, 3);
  Result := ExtractFilePath(JxPath) + ReplaceChar(Name, '.', '_') + '.py';
end;

function OutputNames(const Roots: TStringArray): TStringArray;
var
  i, j, N: Integer;
  Base, Name: string;
  Taken: Boolean;
begin
  SetLength(Result, Length(Roots));
  for i := 0 to High(Roots) do
  begin
    Base := ExtractFileName(ExcludeTrailingPathDelimiter(Roots[i]));
    if Base = '' then
      Base := 'root';
    Name := Base;
    N := 1;
    repeat
      Taken := False;
      for j := 0 to i - 1 do
        if Result[j] = Name then
          Taken := True;
      if Taken then
      begin
        Inc(N);
        Name := Base + '-' + IntToStr(N);
      end;
    until not Taken;
    Result[i] := Name;
  end;
end;

constructor TCompiler.Create(const ARoots, AAutoescape, ATags, APure: TStringArray;
  const AOutput: string = '');
var
  i: Integer;
begin
  SetLength(FRoots, Length(ARoots));
  for i := 0 to High(ARoots) do
    FRoots[i] := IncludeTrailingPathDelimiter(ExpandFileName(ARoots[i]));
  FAutoescape := TStringList.Create;
  FAutoescape.Sorted := True;
  FAutoescape.Duplicates := dupIgnore;
  FAutoescape.CaseSensitive := True;
  for i := 0 to High(AAutoescape) do
    FAutoescape.Add(AAutoescape[i]);
  FTags := TStringList.Create;
  FTags.Sorted := True;
  FTags.Duplicates := dupIgnore;
  FTags.CaseSensitive := True;
  for i := 0 to High(ATags) do
    FTags.Add(ATags[i]);
  FPure := TStringList.Create;
  FPure.Sorted := True;
  FPure.Duplicates := dupIgnore;
  FPure.CaseSensitive := True;
  for i := 0 to High(APure) do
    FPure.Add(APure[i]);
  FOutput := '';
  if AOutput <> '' then
  begin
    FOutput := IncludeTrailingPathDelimiter(ExpandFileName(AOutput));
    FOutNames := OutputNames(FRoots);
  end;
  FCache := TStringList.Create;
  FCache.Sorted := True;
  FCache.CaseSensitive := True;
  FNames := TStringList.Create;
  FNames.Sorted := True;
  FNames.CaseSensitive := True;
end;

destructor TCompiler.Destroy;
var
  i: Integer;
begin
  for i := 0 to FCache.Count - 1 do
    FCache.Objects[i].Free;
  FCache.Free;
  FNames.Free;
  FAutoescape.Free;
  FTags.Free;
  FPure.Free;
  inherited;
end;

(* The extension that decides autoescape is the one before `.jx`, or `jx`
   when there is none: `card.jx` -> jx, `page.html.jx` -> html,
   `mail.txt.jx` -> txt. *)
function TCompiler.IsAutoescaped(const Path: string): Boolean;
var
  Name, Ext: string;
  P: Integer;
begin
  Name := ExtractFileName(Path);
  if EndsWith(Name, '.jx') then
    Delete(Name, Length(Name) - 2, 3);
  P := LastDelimiter('.', Name);
  if P > 0 then
    Ext := LowerCase(Copy(Name, P + 1, MaxInt))
  else
    Ext := 'jx';
  Result := FAutoescape.IndexOf(Ext) >= 0;
end;

(* `_c_<rel path>`, unique across the run: `a/b.jx` and `a_b.jx` would both
   give `_c_a_b`, so the second one gets a numeric suffix. *)
function TCompiler.MangledName(const Path: string; RootIdx: Integer): string;
var
  Rel, Base: string;
  i, N: Integer;
begin
  Rel := Path;
  if StartsWith(Rel, FRoots[RootIdx]) then
    Delete(Rel, 1, Length(FRoots[RootIdx]));
  if EndsWith(Rel, '.jx') then
    Delete(Rel, Length(Rel) - 2, 3);
  for i := 1 to Length(Rel) do
    if not (Rel[i] in NameChars) then
      Rel[i] := '_';
  Base := '_c_' + Rel;
  Result := Base;
  N := 1;
  while FNames.IndexOf(Result) >= 0 do
  begin
    Inc(N);
    Result := Base + '_' + IntToStr(N);
  end;
  FNames.Add(Result);
end;

(* Import rules:
   - `./x.jx`, `../x.jx`: relative to the importing file; it cannot leave the
     folder the importing file was found in.
   - `x.jx`: searched in the folders, in the order given. *)
function TCompiler.ResolveImport(C: TComponent; const D: TImportDecl; out RootIdx: Integer): string;
var
  i: Integer;
  Candidate: string;
begin
  RootIdx := -1;
  if StartsWith(D.Path, '.') then
  begin
    Candidate := ExpandFileName(ExtractFilePath(C.Path) + D.Path);
    if not StartsWith(Candidate, FRoots[C.RootIdx]) then
      CompileError(C.Doc.FileName, C.Doc.Source, D.Pos,
        'Import `' + D.Path + '` goes outside of the folder ' + FRoots[C.RootIdx]);
    if not FileExists(Candidate) then
      CompileError(C.Doc.FileName, C.Doc.Source, D.Pos,
        'Cannot find `' + D.Path + '` (looked for ' + Candidate + ')');
    RootIdx := C.RootIdx;
    Exit(Candidate);
  end;
  if StartsWith(D.Path, '@') then
    CompileError(C.Doc.FileName, C.Doc.Source, D.Pos,
      'Prefixed imports (`@name/...`) are not supported');
  for i := 0 to High(FRoots) do
  begin
    Candidate := ExpandFileName(FRoots[i] + D.Path);
    if StartsWith(Candidate, FRoots[i]) and FileExists(Candidate) then
    begin
      RootIdx := i;
      Exit(Candidate);
    end;
  end;
  CompileError(C.Doc.FileName, C.Doc.Source, D.Pos,
    'Cannot find `' + D.Path + '` in any of the folders');
  Result := '';
end;

function ReadFile(const Path: string): string;
var
  F: TFileStream;
begin
  F := TFileStream.Create(Path, fmOpenRead or fmShareDenyWrite);
  try
    SetLength(Result, F.Size);
    if F.Size > 0 then
      F.ReadBuffer(Result[1], F.Size);
  finally
    F.Free;
  end;
end;

function TCompiler.Load(const Path: string; RootIdx: Integer): TComponent;
var
  Idx, i, DepRoot: Integer;
  Src, Abs, DepPath: string;
  C: TComponent;
begin
  Abs := ExpandFileName(Path);
  Idx := FCache.IndexOf(Abs);
  if Idx >= 0 then
    Exit(TComponent(FCache.Objects[Idx]));

  Src := ReadFile(Abs);
  C := TComponent.Create;
  C.Path := Abs;
  C.RootIdx := RootIdx;
  C.FuncName := MangledName(Abs, RootIdx);
  C.UsesAttrs := Pos('attrs', Src) > 0;
  C.Autoescape := IsAutoescaped(Abs);
  C.Pure := FPure;
  C.RelPath := Abs;
  if StartsWith(C.RelPath, FRoots[RootIdx]) then
    Delete(C.RelPath, 1, Length(FRoots[RootIdx]));
  C.RelPath := ReplaceChar(C.RelPath, '\', '/');
  (* registered before its imports are resolved, so cycles (a component
     importing itself, too) end *)
  FCache.AddObject(Abs, C);
  try
    C.Doc := ParseDocument(Abs, Src, FTags);
    C.Args := ParseDefArgs(C.Doc);
    SetLength(C.Deps, Length(C.Doc.Imports));
    for i := 0 to High(C.Doc.Imports) do
    begin
      C.Deps[i].Alias := C.Doc.Imports[i].Alias;
      DepPath := ResolveImport(C, C.Doc.Imports[i], DepRoot);
      C.Deps[i].Comp := Load(DepPath, DepRoot);
    end;
  except
    (* a broken component must not be served from the cache: the next file
       that imports it reports the same error again *)
    FCache.Delete(FCache.IndexOf(Abs));
    FNames.Delete(FNames.IndexOf(C.FuncName));
    C.Free;
    raise;
  end;
  Result := C;
end;

function TCompiler.ModulePath(const JxPath: string; RootIdx: Integer): string;
var
  Rel: string;
begin
  if FOutput = '' then
    Exit(OutputPath(JxPath));
  Rel := JxPath;
  if StartsWith(Rel, FRoots[RootIdx]) then
    Delete(Rel, 1, Length(FRoots[RootIdx]));
  Result := OutputPath(FOutput + FOutNames[RootIdx] + PathDelim + Rel);
end;

(* 1-based line and 0-based byte column of the 1-based offset Pos in Src *)
procedure LineCol(const Src: string; Pos: Integer; out ALine, ACol: Integer);
var
  i, LineStart: Integer;
begin
  ALine := 1;
  LineStart := 1;
  for i := 1 to Pos - 1 do
    if (i <= Length(Src)) and (Src[i] = #10) then
    begin
      Inc(ALine);
      LineStart := i + 1;
    end;
  ACol := Pos - LineStart;
end;

function TCompiler.CompileModule(C: TComponent; const OutPath: string): string;
var
  Order: array of TComponent;
  Visited, Css, Js, Srcs: TStringList;
  Out, LineMap, Funcs: TBuf;
  Counter, i, k, Lines, FuncLine, JxLine, JxCol, EndLine, EndCol: Integer;
  G: TFuncGen;
  Code: string;
  M: TSrcMapArray;

  procedure Emit(const S: string);
  var
    j: Integer;
  begin
    Out.Add(S);
    for j := 1 to Length(S) do
      if S[j] = #10 then
        Inc(Lines);
  end;

  procedure Visit(X: TComponent);
  var
    k: Integer;
  begin
    if Visited.IndexOf(X.Path) >= 0 then
      Exit;
    Visited.Add(X.Path);
    (* assets in Jx's order: the component's own first, then each import's,
       depth first, without repeats *)
    for k := 0 to High(X.Doc.Css) do
      if Css.IndexOf(X.Doc.Css[k]) < 0 then
        Css.Add(X.Doc.Css[k]);
    for k := 0 to High(X.Doc.Js) do
      if Js.IndexOf(X.Doc.Js[k]) < 0 then
        Js.Add(X.Doc.Js[k]);
    for k := 0 to High(X.Deps) do
      Visit(X.Deps[k].Comp);
    SetLength(Order, Length(Order) + 1);
    Order[High(Order)] := X;
  end;

  function Tuple(L: TStringList): string;
  var
    k: Integer;
  begin
    Result := '(';
    for k := 0 to L.Count - 1 do
      Result := Result + PyStr(L[k]) + ', ';
    Result := Result + ')';
  end;

begin
  SetLength(Order, 0);
  Visited := TStringList.Create;
  Css := TStringList.Create;
  Js := TStringList.Create;
  Srcs := TStringList.Create;
  Out := TBuf.Create;
  LineMap := TBuf.Create;
  Funcs := TBuf.Create;
  Lines := 0;
  try
    Visit(C);
    (* every .jx copied into this module, relative to it, so a catalog can
       tell the module is stale when any of them changes *)
    for i := 0 to High(Order) do
      Srcs.Add(ReplaceChar(
        ExtractRelativePath(ExtractFilePath(OutPath), Order[i].Path), '\', '/'));

    Emit('# Generated by jxc from ' + ExtractFileName(C.Path) + '. Do not edit.'#10);
    (* the `{# def #}` annotations are copied into the signatures; they can
       name types this module does not import (`user: User`) *)
    Emit('from __future__ import annotations'#10);
    Emit('from proper.views.runtime import UNDEFINED, Attrs, Loop, concat, escape, getattr_, getitem, has_attr, mconcat'#10);
    Emit('from proper.views.runtime import Markup as _M, NO_TAGS as _NO_TAGS, escape_output as _e, invalid_prop as _invalid_prop, merge_attrs as _merge_attrs'#10);
    Emit('from proper.views.filters import FILTERS as _FILTERS, FILTERS_AE as _FILTERS_AE'#10);
    Emit('from proper.views.tests import TESTS as _TESTS'#10);
    Emit('from proper.views.runtime import pure_call as _pure, pure_set as _pset'#10);
    Emit(#10'_s = str'#10);
    Emit('_lstrip = str.lstrip'#10);
    (* the results of the calls of `PURE` globals, by call site (and the
       values of its arguments), for this module: one per catalog *)
    Emit('_P = {}'#10#10);
    (* bumped whenever the layout of the module changes, so a catalog can
       tell a module generated by another version *)
    Emit('VIEWS_FORMAT = ' + IntToStr(ModuleFormat) + #10);
    Emit('CSS = ' + Tuple(Css) + #10);
    Emit('JS = ' + Tuple(Js) + #10);
    Emit('SOURCES = ' + Tuple(Srcs) + #10);
    (* the extensions compiled with autoescape, which the catalog compares
       with its own, and whether this module's `render` returns markup *)
    Emit('AUTOESCAPE = ' + Tuple(FAutoescape) + #10);
    Emit('TAGS = ' + Tuple(FTags) + #10);
    Emit('PURE = ' + Tuple(FPure) + #10);
    if C.Autoescape then
      Emit('ESCAPED = True'#10#10)
    else
      Emit('ESCAPED = False'#10#10);
    Counter := 0;
    for i := 0 to High(Order) do
    begin
      G := TFuncGen.Create(Order[i], @Counter);
      try
        Code := G.Generate;
        Emit(#10);
        FuncLine := Lines + 1; (* the line of its `def` *)
        Emit(Code + #10);
        (* (module line, its first column or -1 for all of it, end column,
           source index, template line, first column, end column or -1) *)
        Funcs.Add('    ' + PyStr(Order[i].FuncName) + ': ' + PyStr(Order[i].RelPath) + ','#10);
        M := G.Maps;
        for k := 0 to High(M) do
        begin
          LineCol(Order[i].Doc.Source, M[k].SrcPos, JxLine, JxCol);
          EndCol := -1;
          if M[k].SrcEnd > M[k].SrcPos then
          begin
            LineCol(Order[i].Doc.Source, M[k].SrcEnd, EndLine, EndCol);
            if EndLine <> JxLine then
              EndCol := -1;
          end;
          LineMap.Add('    (' + IntToStr(FuncLine + M[k].Line) + ', ' +
            IntToStr(M[k].PyCol) + ', ' + IntToStr(M[k].PyEnd) + ', ' +
            IntToStr(i) + ', ' + IntToStr(JxLine) + ', ' + IntToStr(JxCol) + ', ' +
            IntToStr(EndCol) + '),'#10);
        end;
      finally
        G.Free;
      end;
    end;
    Emit(#10'render = ' + C.FuncName + #10);
    (* for the tracebacks: see src/proper/views/debug.py *)
    Emit(#10'LINEMAP = ('#10 + LineMap.Join + ')'#10);
    Emit('COMPONENTS = {'#10 + Funcs.Join + '}'#10);
    Result := Out.Join;
  finally
    Out.Free;
    LineMap.Free;
    Funcs.Free;
    Srcs.Free;
    Visited.Free;
    Css.Free;
    Js.Free;
  end;
end;

end.
