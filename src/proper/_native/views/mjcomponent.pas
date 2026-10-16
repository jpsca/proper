(* minijx: a loaded component, as the compiler and the generator share it. *)
unit mjcomponent;

{$mode objfpc}{$H+}

interface

uses
  mjparser;

type
  TComponent = class;

  (* `{# import "path" as Alias #}`, resolved *)
  TDep = record
    Alias: string;
    Comp: TComponent;
  end;

  (* one argument of `{# def #}` *)
  TArg = record
    Name: string;
    Annotation: string;
    Default: string; (* Python source; '' if required *)
    HasDefault: Boolean;
  end;
  TArgArray = array of TArg;

  TComponent = class
  public
    Path: string;     (* absolute *)
    RelPath: string;  (* relative to its root, with `/`: how the catalog names it *)
    RootIdx: Integer; (* the root it was resolved from *)
    FuncName: string; (* the Python function it becomes *)
    Doc: TDocument;
    Deps: array of TDep;
    Args: TArgArray;
    UsesAttrs: Boolean;
    (* its `{{ }}` escape what they render: its extension is one of the
       autoescape ones *)
    Autoescape: Boolean;
    destructor Destroy; override;
    function FindDep(const Alias: string): TComponent;
  end;

implementation

destructor TComponent.Destroy;
begin
  Doc.Free;
  inherited;
end;

function TComponent.FindDep(const Alias: string): TComponent;
var
  i: Integer;
begin
  for i := 0 to High(Deps) do
    if Deps[i].Alias = Alias then
      Exit(Deps[i].Comp);
  Result := nil;
end;

end.
