(* minijx: compile .jx components to Python functions.

  Usage: minijx [--autoescape=EXT,...] [--tags=NAME,...] [--output=DIR] [--only=FILE] FOLDER [FOLDER ...]

  Every `name.jx` under the folders becomes `name.py` next to it; dots in the
  name become `_` (`sitemap.xml.jx` -> `sitemap_xml.py`). Absolute imports
  (`{# import "components/x.jx" as X #}`) are resolved against the folders in
  the order given. Exit code 1 if any file failed to compile, 2 for bad
  arguments.

  `--autoescape` lists the extensions whose components escape what their
  `{{ }}` render: the one before `.jx`, or `jx` if there is none. The
  default is `html,jx,xml`; `--autoescape=` turns it off.

  `--tags` lists the custom tags: `{% name args %}body{% endname %}` calls
  the catalog's function for `name` with the body as a function, `caller`.

  `--output` writes the modules to DIR instead of next to each .jx: those of
  a folder go to DIR/<the folder's name> (`-2`, `-3`... if two have the
  same name), in the same layout.

  `--only` compiles that file alone, one of the folders' .jx; the folders
  are still where its imports are looked for. *)
program minijx;

{$mode objfpc}{$H+}

uses
  SysUtils, Classes, mjerrors, mjutil, mjparser, mjcompiler, mjcomponent;

procedure Usage(const Msg: string = '');
begin
  if Msg <> '' then
    WriteLn(StdErr, 'minijx: ', Msg);
  WriteLn(StdErr, 'usage: minijx [--autoescape=EXT,...] [--tags=NAME,...] [--output=DIR] FOLDER [FOLDER ...]');
  WriteLn(StdErr, '       minijx --version');
  WriteLn(StdErr, '  Compiles every .jx file under the folders to a sibling .py file.');
  WriteLn(StdErr, '  --autoescape: extensions (before .jx; `jx` if none) whose {{ }} are');
  WriteLn(StdErr, '  escaped. Default: html,jx,xml. Empty (`--autoescape=`) turns it off.');
  WriteLn(StdErr, '  --tags: custom block tags, `{% name ... %}...{% endname %}`.');
  WriteLn(StdErr, '  --output: write the modules to DIR/<folder name>/ instead of next to each .jx.');
  WriteLn(StdErr, '  --only: compile FILE alone; the folders are still searched for its imports.');
  Halt(2);
end;

procedure CollectJx(const Dir: string; Files: TStringList);
var
  SR: TSearchRec;
  Path: string;
begin
  if FindFirst(IncludeTrailingPathDelimiter(Dir) + '*', faAnyFile, SR) = 0 then
  begin
    repeat
      if (SR.Name = '.') or (SR.Name = '..') then
        Continue;
      Path := IncludeTrailingPathDelimiter(Dir) + SR.Name;
      if (SR.Attr and faDirectory) <> 0 then
        CollectJx(Path, Files)
      else if EndsWith(SR.Name, '.jx') then
        Files.Add(Path);
    until FindNext(SR) <> 0;
    FindClose(SR);
  end;
end;

(* Written to a temporary file and renamed over the module, so a process
   loading it, or another compiling the same folder at the same time (the
   workers of a server starting), never reads half a module. *)
procedure WriteText(const Path, Text: string);
var
  F: TFileStream;
  Tmp: string;
begin
  Tmp := Path + '.' + IntToStr(GetProcessID) + '.tmp';
  F := TFileStream.Create(Tmp, fmCreate);
  try
    if Text <> '' then
      F.WriteBuffer(Text[1], Length(Text));
  finally
    F.Free;
  end;
  if not RenameFile(Tmp, Path) then
  begin
    DeleteFile(Path);
    if not RenameFile(Tmp, Path) then
    begin
      DeleteFile(Tmp);
      raise EInOutError.Create('Cannot write ' + Path);
    end;
  end;
end;

(* `html, .JX,xml` -> [html, jx, xml]; an invalid extension is a usage error *)
function ParseExtensions(const List: string): TStringArray;
var
  Parts: TStringArray;
  i, j, N: Integer;
  Ext: string;
begin
  SetLength(Result, 0);
  if List = '' then
    Exit;
  Parts := Split(List, ',');
  N := 0;
  for i := 0 to High(Parts) do
  begin
    Ext := LowerCase(Trim(Parts[i]));
    while StartsWith(Ext, '.') do
      Delete(Ext, 1, 1);
    if Ext = '' then
      Continue;
    for j := 1 to Length(Ext) do
      if not (Ext[j] in ['a'..'z', '0'..'9', '_', '-']) then
        Usage('invalid extension for --autoescape: ' + Ext);
    SetLength(Result, N + 1);
    Result[N] := Ext;
    Inc(N);
  end;
end;

(* `cache, other` -> [cache, other]; a name that cannot be a tag is a usage error *)
function ParseTags(const List: string): TStringArray;
var
  Parts: TStringArray;
  i, N: Integer;
  Name, Why: string;
begin
  SetLength(Result, 0);
  if List = '' then
    Exit;
  Parts := Split(List, ',');
  N := 0;
  for i := 0 to High(Parts) do
  begin
    Name := Trim(Parts[i]);
    if Name = '' then
      Continue;
    Why := TagNameError(Name);
    if Why <> '' then
      Usage('`' + Name + '` cannot be a tag: ' + Why);
    SetLength(Result, N + 1);
    Result[N] := Name;
    Inc(N);
  end;
end;

var
  Roots, Autoescape, Tags: TStringArray;
  NRoots: Integer;
  Files: TStringList;
  Outputs: TStringList;    (* output paths already claimed... *)
  OutputSrcs: TStringList; (* ...and the .jx file that claimed each *)
  Compiler: TCompiler;
  i, j, k, Failed, Written: Integer;
  Arg, OutPath, Code, Version, Output, Only: string;
  Comp: TComponent;
begin
  if ParamCount < 1 then
    Usage;
  Autoescape := ParseExtensions('html,jx,xml');
  SetLength(Tags, 0);
  Output := '';
  Only := '';
  SetLength(Roots, ParamCount);
  NRoots := 0;
  for i := 1 to ParamCount do
  begin
    Arg := ParamStr(i);
    if StartsWith(Arg, '--autoescape=') then
    begin
      Autoescape := ParseExtensions(Copy(Arg, Length('--autoescape=') + 1, MaxInt));
      Continue;
    end;
    if StartsWith(Arg, '--output=') then
    begin
      Output := Copy(Arg, Length('--output=') + 1, MaxInt);
      if Output = '' then
        Usage('--output needs a folder');
      Continue;
    end;
    if StartsWith(Arg, '--only=') then
    begin
      Only := ExpandFileName(Copy(Arg, Length('--only=') + 1, MaxInt));
      Continue;
    end;
    if StartsWith(Arg, '--tags=') then
    begin
      Tags := ParseTags(Copy(Arg, Length('--tags=') + 1, MaxInt));
      Continue;
    end;
    if (Arg = '-h') or (Arg = '--help') then
      Usage;
    if Arg = '--version' then
    begin
      (* the runtime reads the format to refuse a binary that generates
         modules it cannot load *)
      Version := MinijxVersion; (* a variable: the constant may be empty *)
      if Version = '' then
        Version := 'unknown';
      WriteLn('minijx ', Version, ' (module format ', ModuleFormat, ')');
      Halt(0);
    end;
    if StartsWith(Arg, '-') then
      Usage('unknown option ' + Arg);
    if not DirectoryExists(Arg) then
    begin
      WriteLn(StdErr, 'minijx: not a folder: ', Arg);
      Halt(2);
    end;
    Roots[NRoots] := IncludeTrailingPathDelimiter(ExpandFileName(Arg));
    Inc(NRoots);
  end;
  SetLength(Roots, NRoots);
  if NRoots = 0 then
    Usage('no folders given');

  Failed := 0;
  Written := 0;
  Compiler := TCompiler.Create(Roots, Autoescape, Tags, Output);
  Files := TStringList.Create;
  Outputs := TStringList.Create;
  OutputSrcs := TStringList.Create;
  try
    for i := 0 to High(Roots) do
    begin
      Files.Clear;
      CollectJx(Roots[i], Files);
      Files.Sort;
      for j := 0 to Files.Count - 1 do
      begin
        if (Only <> '') and (Files[j] <> Only) then
          Continue;
        OutPath := Compiler.ModulePath(Files[j], i);
        try
          k := Outputs.IndexOf(OutPath);
          if k >= 0 then
            raise ECompileError.Create(Files[j], 1, 1, 'Output ' +
              ExtractFileName(OutPath) + ' would overwrite the one compiled from ' +
              OutputSrcs[k]);
          Outputs.Add(OutPath);
          OutputSrcs.Add(Files[j]);
          Comp := Compiler.Load(Files[j], i);
          Code := Compiler.CompileModule(Comp, OutPath);
          ForceDirectories(ExtractFilePath(OutPath));
          WriteText(OutPath, Code);
          Inc(Written);
        except
          on E: ECompileError do
          begin
            WriteLn(StdErr, E.Format);
            Inc(Failed);
          end;
          on E: Exception do
          begin
            WriteLn(StdErr, Files[j], ': ', E.ClassName, ': ', E.Message);
            Inc(Failed);
          end;
        end;
      end;
    end;
  finally
    Files.Free;
    Outputs.Free;
    OutputSrcs.Free;
    Compiler.Free;
  end;
  WriteLn(StdErr, 'minijx: ', Written, ' file(s) written, ', Failed, ' failed');
  (* not Halt(1): the program has to end normally so its strings are freed *)
  if Failed > 0 then
    ExitCode := 1;
end.
