(* minijx: compile errors with a file position. *)
unit mjerrors;

{$mode objfpc}{$H+}

interface

uses
  SysUtils;

type
  ECompileError = class(Exception)
  public
    FileName: string;
    Line: Integer;
    Col: Integer;
    constructor Create(const AFileName: string; ALine, ACol: Integer; const AMsg: string);
    function Format: string;
  end;

(* Convert a 1-based byte offset in Src to a 1-based line and column. *)
procedure OffsetToLineCol(const Src: string; Offset: Integer; out Line, Col: Integer);

(* Raise ECompileError at the given 1-based offset of Src. *)
procedure CompileError(const FileName, Src: string; Offset: Integer; const Msg: string);

implementation

constructor ECompileError.Create(const AFileName: string; ALine, ACol: Integer; const AMsg: string);
begin
  inherited Create(AMsg);
  FileName := AFileName;
  Line := ALine;
  Col := ACol;
end;

function ECompileError.Format: string;
begin
  Result := SysUtils.Format('%s:%d:%d: %s', [FileName, Line, Col, Message]);
end;

procedure OffsetToLineCol(const Src: string; Offset: Integer; out Line, Col: Integer);
var
  i: Integer;
begin
  Line := 1;
  Col := 1;
  if Offset > Length(Src) + 1 then
    Offset := Length(Src) + 1;
  for i := 1 to Offset - 1 do
  begin
    if Src[i] = #10 then
    begin
      Inc(Line);
      Col := 1;
    end
    else
      Inc(Col);
  end;
end;

procedure CompileError(const FileName, Src: string; Offset: Integer; const Msg: string);
var
  Line, Col: Integer;
begin
  OffsetToLineCol(Src, Offset, Line, Col);
  raise ECompileError.Create(FileName, Line, Col, Msg);
end;

end.
