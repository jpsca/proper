{ proper_forms - the parsers of request bodies and headers: urlencoded forms
  (and query strings), header parameters, and multipart/form-data.

  They give what Python needs to make its objects, as offsets and lengths
  (in the input, or in an output buffer for what had to be decoded), and
  never make them: Python decodes the text with the charset of the form.

  - ParseForm reads `name=value&...` as urllib.parse.parse_qs does with
    keep_blank_values: empty pieces skipped, a piece without "=" a name
    with an empty value, "+" a space, %XX decoded and an invalid "%" kept.
  - ParseParams reads `type; key=value; ...` as python-multipart's
    parse_options_header (0.0.32) does: ";" inside quotes doesn't split,
    keys in lowercase, "..." values unquoted, the extended syntax of RFC
    2231 (`key*=`) ignored, as RFC 7578 says for multipart/form-data, and
    a `filename` that is a Windows path cut to its last part (old IE sent
    the whole path).
  - ParseMultipart frames a body as python-multipart does: CR and LF
    skipped before the first boundary, a boundary followed by anything but
    CRLF or "--" read as data, the epilogue ignored, at most 8 headers of
    4224 bytes per part, header names of token characters; then the
    Content-Disposition (name, filename), the Content-Type, and the limits
    of fields, files and field size, in the order python-multipart checks
    them. The boundary is searched with glibc's memmem.

  No managed strings, no exceptions, no heap: Python calls these from its
  own threads (see proper_native.pas). }
unit proper_forms;

{$mode objfpc}{$H+}
{$R-}{$Q-}{$PointerMath On}

interface

const
  TOO_SMALL = -4;
  { ParseMultipart }
  MP_MALFORMED = -10;
  MP_UNFINISHED = -11;
  MP_NO_DISPOSITION = -12;
  MP_NO_NAME = -13;
  MP_TOO_MANY_FIELDS = -14;
  MP_TOO_MANY_FILES = -15;
  MP_FIELD_TOO_BIG = -16;
  MP_HEADERS_TOO_BIG = -17;
  { words (Int64) per record }
  FIELD_WORDS = 4;   { name offset, name length, value offset, value length }
  PARAM_WORDS = 4;   { key offset, key length, value offset, value length }
  PART_WORDS = 10;   { name, filename (-1 none), content-type (-1 none), data,
                       headers: offset and length of each }

{ The fields of an urlencoded text, decoded into Out (at least Len bytes):
  their count, or TOO_SMALL when more than MaxFields. Offsets into Out. }
function ParseForm(Body: PByte; Len: PtrUInt; Out_: PByte; Cap: PtrUInt; Fields: PInt64;
  MaxFields: PtrInt): Int64;
{ The type and parameters of a header value (latin-1), written from Out[OutN]
  on (Cap bytes in all, 2 * Len + 16 is enough): their count, the type
  first (the piece as it is, an empty value), or TOO_SMALL. Offsets into
  Out. }
function ParseParams(P: PByte; Len: PtrUInt; Out_: PByte; Cap: PtrUInt; var OutN: PtrUInt;
  Recs: PInt64; MaxRecs: PtrInt): Int64;
{ The parts of a multipart body: their count, or an MP_ error, or TOO_SMALL
  (more than MaxParts parts, or Out too small). Names and filenames go to
  Out; the content-type, data and headers are offsets into Body. }
function ParseMultipart(Body: PByte; Len: PtrUInt; Boundary: PByte; BLen: PtrUInt;
  Out_: PByte; Cap: PtrUInt; Parts: PInt64; MaxParts: PtrInt; MaxFields, MaxFiles: Int64;
  MaxFieldSize: Int64; Recs: PInt64; MaxRecs: PtrInt): Int64;

implementation

uses
  dynlibs;

type
  TMemmem = function(Hay: Pointer; HayLen: PtrUInt; Needle: Pointer;
    NeedleLen: PtrUInt): Pointer; cdecl;

const
  CR = 13;
  LF = 10;
  MAX_HEADERS = 8;               { python-multipart's DEFAULT_MAX_HEADER_COUNT }
  MAX_HEADER_SIZE = 4096 + 128;  { and DEFAULT_MAX_HEADER_SIZE }

var
  LibC: TLibHandle = NilHandle;
  Memmem: TMemmem = nil;

{ ------------------------------------------------------------- helpers }

function HexVal(C: Byte): Integer; inline;
begin
  case C of
    Ord('0')..Ord('9'): Result := C - Ord('0');
    Ord('a')..Ord('f'): Result := C - Ord('a') + 10;
    Ord('A')..Ord('F'): Result := C - Ord('A') + 10;
  else
    Result := -1;
  end;
end;

{ Src with %XX decoded (and "+" as a space when Plus), at Dst: its length. }
function PercentDecode(Src: PByte; Len: PtrUInt; Plus: Boolean; Dst: PByte): PtrUInt;
var I: PtrUInt; C: Byte; H, L: Integer;
begin
  Result := 0;
  I := 0;
  while I < Len do
  begin
    C := Src[I];
    if (C = Ord('%')) and (I + 2 < Len) then
    begin
      H := HexVal(Src[I + 1]);
      L := HexVal(Src[I + 2]);
      if (H >= 0) and (L >= 0) then
      begin
        Dst[Result] := H * 16 + L;
        Inc(Result);
        Inc(I, 3);
        Continue;
      end;
    end;
    if Plus and (C = Ord('+')) then C := Ord(' ');
    Dst[Result] := C;
    Inc(Result);
    Inc(I);
  end;
end;

{ What Python's str.strip() takes away from a latin-1 text. }
function IsSpace(C: Byte): Boolean; inline;
begin
  Result := (C = 32) or ((C >= 9) and (C <= 13)) or ((C >= $1C) and (C <= $1F))
    or (C = $85) or (C = $A0);
end;

{ str.lower() of a latin-1 character }
function Lower(C: Byte): Byte; inline;
begin
  if ((C >= Ord('A')) and (C <= Ord('Z'))) or ((C >= $C0) and (C <= $DE) and (C <> $D7)) then
    Result := C + 32
  else
    Result := C;
end;

procedure Strip(P: PByte; var Start, Stop: PtrUInt); inline;
begin
  while (Start < Stop) and IsSpace(P[Start]) do Inc(Start);
  while (Stop > Start) and IsSpace(P[Stop - 1]) do Dec(Stop);
end;

{ ---------------------------------------------------------- urlencoded }

function ParseForm(Body: PByte; Len: PtrUInt; Out_: PByte; Cap: PtrUInt; Fields: PInt64;
  MaxFields: PtrInt): Int64;
var I, J, E, N: PtrUInt; Count: PtrInt; F: PInt64;
begin
  if Cap < Len then Exit(TOO_SMALL);
  N := 0;
  Count := 0;
  I := 0;
  while I < Len do
  begin
    J := I;
    while (J < Len) and (Body[J] <> Ord('&')) do Inc(J);
    if J > I then
    begin
      if Count >= MaxFields then Exit(TOO_SMALL);
      E := I;
      while (E < J) and (Body[E] <> Ord('=')) do Inc(E);
      F := @Fields[Count * FIELD_WORDS];
      F[0] := N;
      F[1] := PercentDecode(@Body[I], E - I, True, @Out_[N]);
      Inc(N, F[1]);
      F[2] := N;
      if E < J then
        F[3] := PercentDecode(@Body[E + 1], J - E - 1, True, @Out_[N])
      else
        F[3] := 0;
      Inc(N, F[3]);
      Inc(Count);
    end;
    I := J + 1;
  end;
  Result := Count;
end;

{ ------------------------------------------------------------- params }

{ P[Start..Stop) unquoted, as python-multipart does (a "..." value with
  its \\ and \" unescaped), written at Out[N]: its length. }
function Unquote(P: PByte; Start, Stop: PtrUInt; Out_: PByte; N: PtrUInt;
  Tmp: PByte): PtrUInt;
var I, K, Len: PtrUInt;
begin
  Len := Stop - Start;
  if (Len > 1) and (P[Start] = Ord('"')) and (P[Stop - 1] = Ord('"')) then
  begin
    { .replace('\\\\', '\\') then .replace('\\"', '"'), in that order }
    K := 0;
    I := Start + 1;
    while I < Stop - 1 do
    begin
      if (P[I] = Ord('\')) and (I + 1 < Stop - 1) and (P[I + 1] = Ord('\')) then
      begin
        Tmp[K] := Ord('\');
        Inc(I, 2);
      end
      else
      begin
        Tmp[K] := P[I];
        Inc(I);
      end;
      Inc(K);
    end;
    Result := 0;
    I := 0;
    while I < K do
    begin
      if (Tmp[I] = Ord('\')) and (I + 1 < K) and (Tmp[I + 1] = Ord('"')) then
      begin
        Out_[N + Result] := Ord('"');
        Inc(I, 2);
      end
      else
      begin
        Out_[N + Result] := Tmp[I];
        Inc(I);
      end;
      Inc(Result);
    end;
    Exit;
  end;
  Result := Stop - Start;
  if Result > 0 then Move(P[Start], Out_[N], Result);
end;

{ A filename that is a Windows path, `X:\...` or `\\...`, cut after its
  last backslash, as python-multipart does for old IE. }
procedure CutWindowsPath(Out_: PByte; var Start, VLen: PtrUInt);
var I: PtrUInt;
begin
  if ((VLen >= 3) and (Out_[Start + 1] = Ord(':')) and (Out_[Start + 2] = Ord('\')))
    or ((VLen >= 2) and (Out_[Start] = Ord('\')) and (Out_[Start + 1] = Ord('\'))) then
  begin
    I := Start + VLen;
    while (I > Start) and (Out_[I - 1] <> Ord('\')) do Dec(I);
    VLen := Start + VLen - I;
    Start := I;
  end;
end;

function SameText(A: PByte; ALen: PtrUInt; const B: string): Boolean;
var I: PtrUInt;
begin
  Result := ALen = PtrUInt(Length(B));
  if not Result then Exit;
  for I := 0 to ALen - 1 do
    if A[I] <> Ord(B[I + 1]) then Exit(False);
end;

function ParseParams(P: PByte; Len: PtrUInt; Out_: PByte; Cap: PtrUInt; var OutN: PtrUInt;
  Recs: PInt64; MaxRecs: PtrInt): Int64;
var
  Start, Stop, I, Eq, KS, KE, VS, VE, K, N, KeyLen, VLen, VOff: PtrUInt;
  Quotes, Escaped: PtrInt;
  Count: PtrInt;
  First, Starred: Boolean;
  R: PInt64;
  Tmp: PByte;

  procedure Add(KOff, KLen, VOff_, VLen_: PtrUInt);
  begin
    R := @Recs[Count * PARAM_WORDS];
    R[0] := KOff; R[1] := KLen; R[2] := VOff_; R[3] := VLen_;
    Inc(Count);
  end;

begin
  if Cap < OutN + 2 * Len + 16 then Exit(TOO_SMALL);
  { the scratch of Unquote: the last Len + 1 bytes of Out, past what is
    written (Len + 1 at most) }
  Tmp := @Out_[Cap - Len - 1];
  Count := 0;
  First := True;
  N := OutN;
  Start := 0;
  while True do
  begin
    { the piece ends at the first ";" with the quotes before it balanced
      (a \" doesn't count), as email's _parseparam }
    Quotes := 0;
    Escaped := 0;
    Stop := Start;
    while Stop < Len do
    begin
      if P[Stop] = Ord('"') then
      begin
        Inc(Quotes);
        if (Stop > Start) and (P[Stop - 1] = Ord('\')) then Inc(Escaped);
      end
      else if (P[Stop] = Ord(';')) and ((Quotes - Escaped) mod 2 = 0) then
        Break;
      Inc(Stop);
    end;
    if Count >= MaxRecs then Exit(TOO_SMALL);

    Eq := Start;
    while (Eq < Stop) and (P[Eq] <> Ord('=')) do Inc(Eq);
    KS := Start;
    if Eq = Stop then
    begin
      { no "=": the piece is a key, as it is (not lowercased), with an
        empty value }
      KE := Stop;
      Strip(P, KS, KE);
      K := N;
      if KE > KS then Move(P[KS], Out_[N], KE - KS);
      Inc(N, KE - KS);
      Starred := IndexByte(Out_[K], N - K, Ord('*')) >= 0;
      if First or not Starred then Add(K, N - K, N, 0);
    end
    else
    begin
      KE := Eq;
      Strip(P, KS, KE);
      VS := Eq + 1; VE := Stop;
      Strip(P, VS, VE);
      K := N;
      for I := KS to KE - 1 do
      begin
        Out_[N] := Lower(P[I]);
        Inc(N);
      end;
      KeyLen := N - K;
      if First then
      begin
        { the type is the piece as it is: key=value }
        Out_[N] := Ord('=');
        Inc(N);
        if VE > VS then Move(P[VS], Out_[N], VE - VS);
        Inc(N, VE - VS);
        Add(K, N - K, N, 0);
      end
      { the extended syntax of RFC 2231 (key*=, key*0=...) is ignored:
        RFC 7578 forbids it in multipart/form-data }
      else if IndexByte(Out_[K], KeyLen, Ord('*')) < 0 then
      begin
        VOff := N;
        VLen := Unquote(P, VS, VE, Out_, N, Tmp);
        Inc(N, VLen);
        if SameText(@Out_[K], KeyLen, 'filename') then CutWindowsPath(Out_, VOff, VLen);
        Add(K, KeyLen, VOff, VLen);
      end;
    end;
    First := False;
    if Stop >= Len then Break;
    Start := Stop + 1;
  end;
  OutN := N;
  Result := Count;
end;

{ ------------------------------------------------------------ multipart }

function IsToken(C: Byte): Boolean; inline;
begin
  case Chr(C) of
    'A'..'Z', 'a'..'z', '0'..'9', '!', '#', '$', '%', '&', '''', '*', '+', '-', '.',
    '^', '_', '`', '|', '~': Result := True;
  else
    Result := False;
  end;
end;

function SameName(P: PByte; Len: PtrUInt; const Name: string): Boolean;
var I: PtrUInt;
begin
  Result := Len = PtrUInt(Length(Name));
  if not Result then Exit;
  for I := 0 to Len - 1 do
    if Lower(P[I]) <> Ord(Name[I + 1]) then Exit(False);
end;

function ParseMultipart(Body: PByte; Len: PtrUInt; Boundary: PByte; BLen: PtrUInt;
  Out_: PByte; Cap: PtrUInt; Parts: PInt64; MaxParts: PtrInt; MaxFields, MaxFiles: Int64;
  MaxFieldSize: Int64; Recs: PInt64; MaxRecs: PtrInt): Int64;
var
  I, K, NameStart, ValStart, HdrStart, HdrEnd, DataStart, DLen, OutN, Search, After: PtrUInt;
  DispOff, DispLen, CtOff, CtLen: Int64;
  Headers, Size: PtrInt;
  Count: PtrInt;
  Fields, Files: Int64;
  NParams, J: Int64;
  NameRec, FileRec: Int64;
  IsFile, Final: Boolean;
  Found: PByte;
  Part, R: PInt64;
  Delim: array[0..259] of Byte;
  C: Byte;
begin
  if (BLen = 0) or (BLen > 256) then Exit(MP_MALFORMED);
  { the delimiter of a part's end: CRLF "--" boundary }
  Delim[0] := CR; Delim[1] := LF; Delim[2] := Ord('-'); Delim[3] := Ord('-');
  Move(Boundary^, Delim[4], BLen);
  DLen := BLen + 4;

  I := 0;
  if Len = 0 then Exit(MP_UNFINISHED);
  if (Body[0] = CR) or (Body[0] = LF) then
  begin
    while (I < Len) and (Body[I] <> Ord('-')) do Inc(I);
    if I >= Len then Exit(MP_UNFINISHED);
  end;
  { the first boundary: "--" boundary, then CRLF, or "--" for an empty form }
  for K := 2 to DLen - 1 do
  begin
    if I >= Len then Exit(MP_UNFINISHED);
    if Body[I] <> Delim[K] then Exit(MP_MALFORMED);
    Inc(I);
  end;
  if I >= Len then Exit(MP_UNFINISHED);
  if Body[I] = Ord('-') then
  begin
    if I + 1 >= Len then Exit(MP_UNFINISHED);
    if Body[I + 1] <> Ord('-') then Exit(MP_MALFORMED);
    Exit(0);
  end;
  if Body[I] <> CR then Exit(MP_MALFORMED);
  if I + 1 >= Len then Exit(MP_UNFINISHED);
  if Body[I + 1] <> LF then Exit(MP_MALFORMED);
  Inc(I, 2);

  Count := 0;
  Fields := 0;
  Files := 0;
  OutN := 0;
  while True do
  begin
    if Count >= MaxParts then Exit(TOO_SMALL);
    { the headers }
    HdrStart := I;
    Headers := 0;
    DispOff := -1; DispLen := 0;
    CtOff := -1; CtLen := 0;
    while True do
    begin
      if I >= Len then Exit(MP_UNFINISHED);
      if Body[I] = CR then
      begin
        if I + 1 >= Len then Exit(MP_UNFINISHED);
        if Body[I + 1] <> LF then Exit(MP_MALFORMED);
        HdrEnd := I;
        Inc(I, 2);
        Break;
      end;
      Inc(Headers);
      if Headers > MAX_HEADERS then Exit(MP_HEADERS_TOO_BIG);
      NameStart := I;
      Size := 0;
      while True do
      begin
        if I >= Len then Exit(MP_UNFINISHED);
        C := Body[I];
        Inc(Size);
        if Size > MAX_HEADER_SIZE then Exit(MP_HEADERS_TOO_BIG);
        if C = Ord(':') then Break;
        if not IsToken(C) then Exit(MP_MALFORMED);
        Inc(I);
      end;
      if I = NameStart then Exit(MP_MALFORMED);  { a header with no name }
      K := I;  { the name ends here }
      Inc(I);
      while (I < Len) and (Body[I] = Ord(' ')) do
      begin
        Inc(Size);
        if Size > MAX_HEADER_SIZE then Exit(MP_HEADERS_TOO_BIG);
        Inc(I);
      end;
      ValStart := I;
      while (I < Len) and (Body[I] <> CR) do
      begin
        Inc(Size);
        if Size > MAX_HEADER_SIZE then Exit(MP_HEADERS_TOO_BIG);
        Inc(I);
      end;
      if I + 1 >= Len then Exit(MP_UNFINISHED);
      if Body[I + 1] <> LF then Exit(MP_MALFORMED);
      if (DispOff < 0) and SameName(@Body[NameStart], K - NameStart, 'content-disposition') then
      begin
        DispOff := ValStart;
        DispLen := I - ValStart;
      end
      else if (CtOff < 0) and SameName(@Body[NameStart], K - NameStart, 'content-type') then
      begin
        CtOff := ValStart;
        CtLen := I - ValStart;
      end;
      Inc(I, 2);
    end;

    { name and filename }
    if (DispOff < 0) or (DispLen = 0) then Exit(MP_NO_DISPOSITION);
    NameRec := -1;
    FileRec := -1;
    if IndexByte(Body[DispOff], DispLen, Ord(';')) >= 0 then
    begin
      NParams := ParseParams(@Body[DispOff], DispLen, Out_, Cap, OutN, Recs, MaxRecs);
      if NParams < 0 then Exit(NParams);
      for J := 1 to NParams - 1 do
      begin
        R := @Recs[J * PARAM_WORDS];
        if SameText(@Out_[R[0]], R[1], 'name') then NameRec := J
        else if SameText(@Out_[R[0]], R[1], 'filename') then FileRec := J;
      end;
    end;
    if NameRec < 0 then Exit(MP_NO_NAME);
    IsFile := FileRec >= 0;
    if IsFile then
    begin
      Inc(Files);
      if Files > MaxFiles then Exit(MP_TOO_MANY_FILES);
    end
    else
    begin
      Inc(Fields);
      if Fields > MaxFields then Exit(MP_TOO_MANY_FIELDS);
    end;

    { the data, up to a delimiter followed by CRLF (another part) or "--"
      (the last); one followed by anything else is data }
    DataStart := I;
    Search := I;
    Final := False;
    while True do
    begin
      if Search >= Len then Found := nil
      else Found := Memmem(@Body[Search], Len - Search, @Delim[0], DLen);
      if Found = nil then
      begin
        if (not IsFile) and (Int64(Len - DataStart) > MaxFieldSize) then
          Exit(MP_FIELD_TOO_BIG);
        Exit(MP_UNFINISHED);
      end;
      K := PtrUInt(Found - Body);
      After := K + DLen;
      if After + 1 >= Len then
      begin
        if (not IsFile) and (Int64(K - DataStart) > MaxFieldSize) then
          Exit(MP_FIELD_TOO_BIG);
        Exit(MP_UNFINISHED);
      end;
      if (Body[After] = CR) and (Body[After + 1] = LF) then Break;
      if (Body[After] = Ord('-')) and (Body[After + 1] = Ord('-')) then
      begin
        Final := True;
        Break;
      end;
      Search := K + 1;
    end;
    if (not IsFile) and (Int64(K - DataStart) > MaxFieldSize) then Exit(MP_FIELD_TOO_BIG);

    Part := @Parts[Count * PART_WORDS];
    R := @Recs[NameRec * PARAM_WORDS];
    Part[0] := R[2]; Part[1] := R[3];
    if IsFile then
    begin
      R := @Recs[FileRec * PARAM_WORDS];
      Part[2] := R[2]; Part[3] := R[3];
      Part[4] := CtOff; Part[5] := CtLen;
    end
    else
    begin
      Part[2] := -1; Part[3] := 0;
      Part[4] := -1; Part[5] := 0;
    end;
    Part[6] := DataStart; Part[7] := K - DataStart;
    Part[8] := HdrStart; Part[9] := HdrEnd - HdrStart;
    Inc(Count);
    if Final then Exit(Count);
    I := After + 2;
  end;
end;

initialization
  LibC := LoadLibrary('libc.so.6');
  if LibC <> NilHandle then
    Memmem := TMemmem(GetProcedureAddress(LibC, 'memmem'));

end.
