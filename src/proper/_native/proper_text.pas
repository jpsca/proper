{ proper_text - HTML to plain text: the text version of an HTML email, and
  `str()` of a rich text document.

  The HTML is read as Python's html.parser.HTMLParser (3.14) reads it with
  convert_charrefs: the same tags, attributes and text, the text decoded as
  html.unescape decodes it (the named references of HTML5, from
  proper_entities.inc), the attribute values as HTMLParser decodes them,
  the content of script, style, xmp, iframe, noembed and noframes as raw
  text, and of title and textarea as escapable raw text. A tag that isn't
  closed when the HTML ends drops what is left, as HTMLParser does.

  What each tag gives:
  - script, style, template, noscript, iframe, canvas and title: nothing,
    with what is in them.
  - The blocks (tBlock in KNOWN_TAGS): a blank line before and after.
  - li: a line starting with "- ". br: a new line (two in a row at most).
    hr: a line of 20 "-".
  - pre: its text as it is, between lines of "```". code (out of a pre):
    its text between "`".
  - a with an href: its text, then the href in parentheses, unless the
    href is the text.
  - img with an alt: "[alt]".
  - proper-attachment: "[...]" with its alt, its caption, or the filename
    of its sgid (in Names), or "[file]".
  - Out of a pre, a run of spaces, tabs or new lines is one space; there is
    no space at the start or the end of a line, at most one blank line in a
    row, and nothing blank at the start or the end. In a pre, CR and CRLF
    are LF, and the LF right after <pre> is dropped.

  The UTF-8 of the HTML is read byte by byte: every class of characters
  the parser looks for is ASCII, or all but some ASCII. Where code points
  matter, they are counted: the 32 characters of a named reference, the
  Unicode whitespace of str.strip(), and the KELVIN SIGN, which str.lower()
  makes "k".

  No managed strings, no exceptions, no heap: Python calls this from its
  own threads (see proper_native.pas). }
unit proper_text;

{$mode objfpc}{$H+}
{$R-}{$Q-}{$PointerMath On}

interface

const
  { words (Int64) per record }
  NAME_WORDS = 4;   { sgid offset, sgid length, filename offset, filename length }
  LINK_WORDS = 3;   { href offset in Scratch, href length (-1 none), text start in Out }

{ The text of Html, written to Out: its length, or TOO_SMALL (-4) when Out
  or Scratch is too small, or more than LinksCap links are open at once.
  Names and NameRecs: the filename of each attachment, by its sgid. }
function Html2Text(Html: PByte; Len: PtrUInt; Names: PByte; NameRecs: PInt64;
  NameCount: PtrInt; Out_: PByte; Cap: PtrUInt; Scratch: PByte; ScratchCap: PtrUInt;
  Links: PInt64; LinksCap: PtrInt): Int64;

implementation

{$I proper_entities.inc}

const
  TOO_SMALL = -4;
  TAB = 9; LF = 10; FF = 12; CR = 13; SP = 32;
  HR_WIDTH = 20;
  MAX_TAG = 17;   { "proper-attachment" }

type
  TTag = (tOther, tSkip, tBlock, tA, tBr, tCode, tHr, tImg, tLi, tPre, tAttachment);
  TCdata = (cdNone, cdRaw, cdEscapable, cdPlaintext);
  TAttr = (aOther, aHref, aAlt, aCaption, aSgid);

  { An attribute: where its value is (Has: it has one, `name=...`) }
  TAttrValue = record
    Seen, Has: Boolean;
    At, Len: PtrUInt;
  end;
  TAttrs = array[aHref..aSgid] of TAttrValue;

  TKnownTag = record
    Name: string[MAX_TAG];
    Tag: TTag;
    Cdata: TCdata;
  end;

  TState = record
    Html: PByte;
    Len: PtrUInt;
    Out_: PByte;
    Cap, N: PtrUInt;
    Scratch: PByte;
    ScratchCap, ScratchTop: PtrUInt;
    Links: PInt64;
    LinksCap, LinkCount: PtrInt;
    Names: PByte;
    NameRecs: PInt64;
    NameCount: PtrInt;
    Overflow: Boolean;
    { the writer }
    PendingNl: PtrInt;      { new lines owed before the next character }
    PendingSpace: Boolean;  { a space owed before the next character }
    TrailNl: PtrUInt;       { new lines at the end of Out }
    LastCr: Boolean;        { in a pre, the last character was a CR }
    DropNl: Boolean;        { in a pre, drop a LF that comes first }
    { the reader }
    Skip, PreDepth: PtrInt;
    AfterPre: Boolean;      { the last event was <pre> }
    Cdata: TCdata;
    CdataName: PChar;
    CdataLen: PtrUInt;
  end;

const
  { The tags that give something, and the elements whose content is raw
    text, sorted by their bytes }
  KNOWN_TAGS: array[0..51] of TKnownTag = (
    (Name: 'a'; Tag: tA; Cdata: cdNone),
    (Name: 'address'; Tag: tBlock; Cdata: cdNone),
    (Name: 'article'; Tag: tBlock; Cdata: cdNone),
    (Name: 'aside'; Tag: tBlock; Cdata: cdNone),
    (Name: 'blockquote'; Tag: tBlock; Cdata: cdNone),
    (Name: 'br'; Tag: tBr; Cdata: cdNone),
    (Name: 'canvas'; Tag: tSkip; Cdata: cdNone),
    (Name: 'code'; Tag: tCode; Cdata: cdNone),
    (Name: 'dd'; Tag: tBlock; Cdata: cdNone),
    (Name: 'details'; Tag: tBlock; Cdata: cdNone),
    (Name: 'dialog'; Tag: tBlock; Cdata: cdNone),
    (Name: 'div'; Tag: tBlock; Cdata: cdNone),
    (Name: 'dl'; Tag: tBlock; Cdata: cdNone),
    (Name: 'dt'; Tag: tBlock; Cdata: cdNone),
    (Name: 'fieldset'; Tag: tBlock; Cdata: cdNone),
    (Name: 'figcaption'; Tag: tBlock; Cdata: cdNone),
    (Name: 'figure'; Tag: tBlock; Cdata: cdNone),
    (Name: 'footer'; Tag: tBlock; Cdata: cdNone),
    (Name: 'form'; Tag: tBlock; Cdata: cdNone),
    (Name: 'h1'; Tag: tBlock; Cdata: cdNone),
    (Name: 'h2'; Tag: tBlock; Cdata: cdNone),
    (Name: 'h3'; Tag: tBlock; Cdata: cdNone),
    (Name: 'h4'; Tag: tBlock; Cdata: cdNone),
    (Name: 'h5'; Tag: tBlock; Cdata: cdNone),
    (Name: 'h6'; Tag: tBlock; Cdata: cdNone),
    (Name: 'header'; Tag: tBlock; Cdata: cdNone),
    (Name: 'hr'; Tag: tHr; Cdata: cdNone),
    (Name: 'iframe'; Tag: tSkip; Cdata: cdRaw),
    (Name: 'img'; Tag: tImg; Cdata: cdNone),
    (Name: 'li'; Tag: tLi; Cdata: cdNone),
    (Name: 'main'; Tag: tBlock; Cdata: cdNone),
    (Name: 'menu'; Tag: tBlock; Cdata: cdNone),
    (Name: 'nav'; Tag: tBlock; Cdata: cdNone),
    (Name: 'noembed'; Tag: tOther; Cdata: cdRaw),
    (Name: 'noframes'; Tag: tOther; Cdata: cdRaw),
    (Name: 'noscript'; Tag: tSkip; Cdata: cdNone),
    (Name: 'ol'; Tag: tBlock; Cdata: cdNone),
    (Name: 'output'; Tag: tBlock; Cdata: cdNone),
    (Name: 'p'; Tag: tBlock; Cdata: cdNone),
    (Name: 'plaintext'; Tag: tOther; Cdata: cdPlaintext),
    (Name: 'pre'; Tag: tPre; Cdata: cdNone),
    (Name: 'proper-attachment'; Tag: tAttachment; Cdata: cdNone),
    (Name: 'script'; Tag: tSkip; Cdata: cdRaw),
    (Name: 'section'; Tag: tBlock; Cdata: cdNone),
    (Name: 'style'; Tag: tSkip; Cdata: cdRaw),
    (Name: 'table'; Tag: tBlock; Cdata: cdNone),
    (Name: 'template'; Tag: tSkip; Cdata: cdNone),
    (Name: 'textarea'; Tag: tOther; Cdata: cdEscapable),
    (Name: 'title'; Tag: tSkip; Cdata: cdEscapable),
    (Name: 'tr'; Tag: tBlock; Cdata: cdNone),
    (Name: 'ul'; Tag: tBlock; Cdata: cdNone),
    (Name: 'xmp'; Tag: tOther; Cdata: cdRaw));

  { html.unescape's _invalid_charrefs from 0x80 on }
  WINDOWS_1252: array[$80..$9F] of Word = (
    $20AC, $81, $201A, $0192, $201E, $2026, $2020, $2021, $02C6, $2030, $0160, $2039,
    $0152, $8D, $017D, $8F, $90, $2018, $2019, $201C, $201D, $2022, $2013, $2014,
    $02DC, $2122, $0161, $203A, $0153, $9D, $017E, $0178);

{ ------------------------------------------------------------- helpers }

function IsHtmlSpace(C: Byte): Boolean; inline;
begin
  Result := (C = SP) or (C = TAB) or (C = LF) or (C = FF) or (C = CR);
end;

function IsLetter(C: Byte): Boolean; inline;
begin
  Result := ((C >= Ord('a')) and (C <= Ord('z'))) or ((C >= Ord('A')) and (C <= Ord('Z')));
end;

function IsDigit(C: Byte): Boolean; inline;
begin
  Result := (C >= Ord('0')) and (C <= Ord('9'));
end;

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

function LowerAscii(C: Byte): Byte; inline;
begin
  if (C >= Ord('A')) and (C <= Ord('Z')) then Result := C + 32 else Result := C;
end;

{ The bytes of the code point at P (valid UTF-8) }
function CharLen(P: PByte; Avail: PtrUInt): PtrUInt; inline;
begin
  Result := 1;
  while (Result < Avail) and ((P[Result] and $C0) = $80) do Inc(Result);
end;

{ The length of the str.isspace() code point at P, or 0 }
function PySpaceLen(P: PByte; Avail: PtrUInt): PtrUInt;
begin
  Result := 0;
  case P[0] of
    9..13, $1C..$1F, SP: Result := 1;
    $C2: if (Avail >= 2) and ((P[1] = $85) or (P[1] = $A0)) then Result := 2;
    $E1: if (Avail >= 3) and (P[1] = $9A) and (P[2] = $80) then Result := 3;
    $E2:
      if Avail >= 3 then
        if (P[1] = $80) and ((P[2] <= $8A) or (P[2] = $A8) or (P[2] = $A9) or (P[2] = $AF)) then
          Result := 3
        else if (P[1] = $81) and (P[2] = $9F) then
          Result := 3;
    $E3: if (Avail >= 3) and (P[1] = $80) and (P[2] = $80) then Result := 3;
  end;
end;

{ The index of byte C in P[From, To), or -1 }
function FindByte(P: PByte; From, To_: PtrUInt; C: Byte): PtrInt; inline;
var K: PtrInt;
begin
  if From >= To_ then Exit(-1);
  K := IndexByte(P[From], To_ - From, C);
  if K < 0 then Result := -1 else Result := From + K;
end;

function SameBytes(A: PByte; ALen: PtrUInt; const B: ShortString): Boolean;
var I: PtrUInt;
begin
  if ALen <> Length(B) then Exit(False);
  if ALen = 0 then Exit(True);
  for I := 0 to ALen - 1 do
    if A[I] <> Ord(B[I + 1]) then Exit(False);
  Result := True;
end;

{ ------------------------------------------------------------- entities }

{ The index of the entity named P[0, Len) (with its ";", if it has one), or -1 }
function FindEntity(P: PByte; Len: PtrUInt): PtrInt;
var Lo, Hi, Mid: PtrInt; K: PByte; KLen, I, M: PtrUInt; Cmp: Integer;
begin
  if Len = 0 then Exit(-1);
  Lo := ENTITY_FIRST[P[0]];
  Hi := ENTITY_FIRST[P[0] + 1] - 1;
  while Lo <= Hi do
  begin
    Mid := (Lo + Hi) div 2;
    K := @ENTITY_KEYS[ENTITY_KEY_AT[Mid]];
    KLen := ENTITY_KEY_AT[Mid + 1] - ENTITY_KEY_AT[Mid];
    M := KLen;
    if Len < M then M := Len;
    Cmp := 0;
    I := 0;
    while (I < M) and (Cmp = 0) do
    begin
      Cmp := Integer(P[I]) - Integer(K[I]);
      Inc(I);
    end;
    if Cmp = 0 then
      if Len < KLen then Cmp := -1
      else if Len > KLen then Cmp := 1;
    if Cmp = 0 then Exit(Mid);
    if Cmp < 0 then Hi := Mid - 1 else Lo := Mid + 1;
  end;
  Result := -1;
end;

{ ------------------------------------------------------------- the writer }

procedure Put(var S: TState; C: Byte); inline;
begin
  if S.N < S.Cap then S.Out_[S.N] := C else S.Overflow := True;
  Inc(S.N);
  if C = LF then Inc(S.TrailNl) else S.TrailNl := 0;
  S.LastCr := False;
end;

{ What is owed before a character: the new lines, or the space }
procedure Flush(var S: TState);
var K: PtrInt;
begin
  if S.PendingNl > 0 then
  begin
    if S.N > 0 then
      for K := PtrInt(S.TrailNl) + 1 to S.PendingNl do Put(S, LF);
    S.PendingNl := 0;
    S.PendingSpace := False;
  end
  else if S.PendingSpace then
  begin
    S.PendingSpace := False;
    Put(S, SP);
  end;
end;

{ A byte of text out of a pre }
procedure TextByte(var S: TState; C: Byte);
begin
  if IsHtmlSpace(C) then
  begin
    if (S.N > 0) and (S.PendingNl = 0) and (S.TrailNl = 0) then S.PendingSpace := True;
  end
  else
  begin
    Flush(S);
    Put(S, C);
  end;
end;

{ A byte of text in a pre }
procedure LiteralByte(var S: TState; C: Byte);
begin
  if S.DropNl then
  begin
    S.DropNl := False;
    if C = LF then Exit;
    if C = CR then
    begin
      S.LastCr := True;
      Exit;
    end;
  end;
  if C = CR then
  begin
    Flush(S);
    Put(S, LF);
    S.LastCr := True;
  end
  else if C = LF then
  begin
    if S.LastCr then S.LastCr := False
    else
    begin
      Flush(S);
      Put(S, LF);
    end;
  end
  else
  begin
    Flush(S);
    Put(S, C);
  end;
end;

procedure Emit(var S: TState; C: Byte); inline;
begin
  if S.PreDepth > 0 then LiteralByte(S, C) else TextByte(S, C);
end;

{ Bytes that need nothing but Put: after what is owed, as they are }
procedure PutRun(var S: TState; P: PByte; L: PtrUInt);
var Room: PtrUInt;
begin
  Flush(S);
  if S.N < S.Cap then Room := S.Cap - S.N else Room := 0;
  if L <= Room then Move(P^, S.Out_[S.N], L) else S.Overflow := True;
  Inc(S.N, L);
  S.TrailNl := 0;
  S.LastCr := False;
end;

procedure EmitBytes(var S: TState; P: PByte; L: PtrUInt);
var I, J: PtrUInt;
begin
  I := 0;
  while I < L do
    if (P[I] = LF) or (P[I] = CR) or S.DropNl or ((S.PreDepth = 0) and IsHtmlSpace(P[I])) then
    begin
      Emit(S, P[I]);
      Inc(I);
    end
    else
    begin
      { a run of bytes that are written as they are }
      J := I + 1;
      if S.PreDepth > 0 then
        while (J < L) and (P[J] <> LF) and (P[J] <> CR) do Inc(J)
      else
        while (J < L) and not IsHtmlSpace(P[J]) do Inc(J);
      PutRun(S, P + I, J - I);
      I := J;
    end;
end;

procedure EmitStr(var S: TState; const T: ShortString);
var I: Integer;
begin
  for I := 1 to Length(T) do Emit(S, Ord(T[I]));
end;

procedure Block(var S: TState); inline;
begin
  S.PendingSpace := False;
  if S.PendingNl < 2 then S.PendingNl := 2;
end;

procedure Line(var S: TState); inline;
begin
  S.PendingSpace := False;
  if S.PendingNl < 1 then S.PendingNl := 1;
end;

procedure Br(var S: TState); inline;
var K: PtrInt;
begin
  S.PendingSpace := False;
  K := S.PendingNl;
  if PtrInt(S.TrailNl) > K then K := S.TrailNl;
  Inc(K);
  if K > 2 then K := 2;
  S.PendingNl := K;
end;

{ ------------------------------------------------------------- references }

{ What the numeric reference &#Num; is, as html.unescape decodes it }
procedure CharRef(var S: TState; Num: QWord; Write: Boolean; Dst: PByte; var DLen: PtrUInt;
  DCap: PtrUInt);

  procedure Out1(C: Byte);
  begin
    if Write then Emit(S, C)
    else
    begin
      if DLen < DCap then Dst[DLen] := C else S.Overflow := True;
      Inc(DLen);
    end;
  end;

  procedure OutCode(Code: LongWord);
  begin
    if Code < $80 then Out1(Code)
    else if Code < $800 then
    begin
      Out1($C0 or (Code shr 6)); Out1($80 or (Code and $3F));
    end
    else if Code < $10000 then
    begin
      Out1($E0 or (Code shr 12)); Out1($80 or ((Code shr 6) and $3F));
      Out1($80 or (Code and $3F));
    end
    else
    begin
      Out1($F0 or (Code shr 18)); Out1($80 or ((Code shr 12) and $3F));
      Out1($80 or ((Code shr 6) and $3F)); Out1($80 or (Code and $3F));
    end;
  end;

var Code: LongWord;
begin
  if Num > $110000 then Code := $110000 else Code := Num;
  case Code of
    0: OutCode($FFFD);
    $0D: Out1(CR);
    $80..$9F: OutCode(WINDOWS_1252[Code]);
    $D800..$DFFF, $110000: OutCode($FFFD);
    $1..$8, $B, $E..$1F, $7F, $FDD0..$FDEF: ;   { dropped }
  else
    if (Code and $FFFE) = $FFFE then Exit;   { U+xFFFE and U+xFFFF }
    OutCode(Code);
  end;
end;

{ The digits of a numeric reference from P[I] (decimal, or hex), up to To_:
  its value, capped past U+10FFFF }
function RefNumber(P: PByte; var I: PtrUInt; To_: PtrUInt; Hex: Boolean): QWord;
var D: Integer;
begin
  Result := 0;
  while I < To_ do
  begin
    if Hex then D := HexVal(P[I])
    else if IsDigit(P[I]) then D := P[I] - Ord('0')
    else D := -1;
    if D < 0 then Break;
    if Result <= $110000 then
      if Hex then Result := Result * 16 + D else Result := Result * 10 + D;
    Inc(I);
  end;
end;

{ Text decoded as html.unescape decodes it, emitted }
procedure EmitUnescaped(var S: TState; P: PByte; From, To_: PtrUInt);
var
  I, J, NameEnd, RefEnd, Count, Ascii, X: PtrUInt; Num: QWord; E: PtrInt; Hex: Boolean;
  Unused: PtrUInt;
begin
  I := From;
  while I < To_ do
  begin
    J := I;
    while (J < To_) and (P[J] <> Ord('&')) do Inc(J);
    EmitBytes(S, P + I, J - I);
    I := J;
    if I >= To_ then Break;
    { at "&" }
    if (I + 1 < To_) and (P[I + 1] = Ord('#')) then
    begin
      Hex := (I + 3 < To_) and ((P[I + 2] = Ord('x')) or (P[I + 2] = Ord('X'))) and
        (HexVal(P[I + 3]) >= 0);
      if (I + 2 < To_) and IsDigit(P[I + 2]) then
      begin
        J := I + 2;
        Num := RefNumber(P, J, To_, False);
      end
      else if Hex then
      begin
        J := I + 3;
        Num := RefNumber(P, J, To_, True);
      end
      else
      begin
        { "&#" and no digit: not a reference }
        Emit(S, Ord('&'));
        Inc(I);
        Continue;
      end;
      if (J < To_) and (P[J] = Ord(';')) then Inc(J);
      Unused := 0;
      CharRef(S, Num, True, nil, Unused, 0);
      I := J;
      Continue;
    end;
    { a name: 1 to 32 code points of [^\t\n\f <&#;], and a ";" }
    J := I + 1;
    Count := 0;
    Ascii := 0;
    while (J < To_) and (Count < 32) do
    begin
      case P[J] of
        TAB, LF, FF, SP, Ord('<'), Ord('&'), Ord('#'), Ord(';'): Break;
      end;
      if (P[J] < $80) and (Ascii = Count) then Inc(Ascii);
      Inc(J, CharLen(P + J, To_ - J));
      Inc(Count);
    end;
    if Count = 0 then
    begin
      Emit(S, Ord('&'));
      Inc(I);
      Continue;
    end;
    NameEnd := J;
    RefEnd := J;
    if (J < To_) and (P[J] = Ord(';')) then RefEnd := J + 1;
    E := -1;
    if Ascii = Count then E := FindEntity(P + I + 1, RefEnd - I - 1);
    if E >= 0 then
      EmitBytes(S, @ENTITY_VALUES[ENTITY_VALUE_AT[E]],
        ENTITY_VALUE_AT[E + 1] - ENTITY_VALUE_AT[E])
    else
    begin
      { the longest name that is a prefix, of 2 characters or more }
      X := Count;
      if RefEnd > NameEnd then X := Count + 1;
      Dec(X);
      if X > Ascii then X := Ascii;
      while X >= 2 do
      begin
        E := FindEntity(P + I + 1, X);
        if E >= 0 then Break;
        Dec(X);
      end;
      if (X >= 2) and (E >= 0) then
      begin
        EmitBytes(S, @ENTITY_VALUES[ENTITY_VALUE_AT[E]],
          ENTITY_VALUE_AT[E + 1] - ENTITY_VALUE_AT[E]);
        EmitBytes(S, P + I + 1 + X, RefEnd - (I + 1 + X));
      end
      else
        EmitBytes(S, P + I, RefEnd - I);
    end;
    I := RefEnd;
  end;
end;

{ An attribute value decoded as HTMLParser decodes it, written to the
  Scratch from ScratchTop on: its length }
function UnescapeAttr(var S: TState; From, To_: PtrUInt): PtrUInt;
var
  P, Dst: PByte; I, J, K, DCap, DLen: PtrUInt; Num: QWord; E: PtrInt;

  procedure Out1(C: Byte);
  begin
    if DLen < DCap then Dst[DLen] := C else S.Overflow := True;
    Inc(DLen);
  end;

  procedure OutBytes(Q: PByte; L: PtrUInt);
  var M: PtrUInt;
  begin
    M := 0;
    while M < L do
    begin
      Out1(Q[M]);
      Inc(M);
    end;
  end;

begin
  DLen := 0;
  P := S.Html;
  Dst := S.Scratch + S.ScratchTop;
  if S.ScratchTop < S.ScratchCap then DCap := S.ScratchCap - S.ScratchTop else DCap := 0;
  I := From;
  while I < To_ do
  begin
    if P[I] <> Ord('&') then
    begin
      Out1(P[I]);
      Inc(I);
      Continue;
    end;
    if (I + 2 < To_) and (P[I + 1] = Ord('#')) and
      (IsDigit(P[I + 2]) or (((P[I + 2] = Ord('x')) or (P[I + 2] = Ord('X'))) and
        (I + 3 < To_) and (HexVal(P[I + 3]) >= 0))) then
    begin
      if IsDigit(P[I + 2]) then
      begin
        J := I + 2;
        Num := RefNumber(P, J, To_, False);
      end
      else
      begin
        J := I + 3;
        Num := RefNumber(P, J, To_, True);
      end;
      if (J < To_) and (P[J] = Ord(';')) then Inc(J);
      CharRef(S, Num, False, Dst, DLen, DCap);
      I := J;
      Continue;
    end;
    if (I + 1 < To_) and IsLetter(P[I + 1]) then
    begin
      J := I + 2;
      while (J < To_) and (IsLetter(P[J]) or IsDigit(P[J])) do Inc(J);
      K := J;   { the end of the reference }
      E := -1;
      if (J < To_) and (P[J] = Ord('=')) then
        K := J   { kept as it is }
      else
      begin
        if (J < To_) and (P[J] = Ord(';')) then K := J + 1;
        E := FindEntity(P + I + 1, K - I - 1);
      end;
      if E >= 0 then
        OutBytes(@ENTITY_VALUES[ENTITY_VALUE_AT[E]], ENTITY_VALUE_AT[E + 1] - ENTITY_VALUE_AT[E])
      else
        OutBytes(P + I, K - I);
      I := K;
      Continue;
    end;
    Out1(Ord('&'));
    Inc(I);
  end;
  Result := DLen;
end;

{ ------------------------------------------------------------- the tags }

{ The tag of a name, lowered as str.lower() lowers it; with Cdata, the
  name of the element whose raw text it starts (CdataName, CdataLen) }
function TagOf(P: PByte; Len: PtrUInt; out Cdata: TCdata; out CdataName: PChar;
  out CdataLen: PtrUInt): TTag;
var
  Name: array[0..MAX_TAG - 1] of Byte; L, I, M: PtrUInt; Lo, Hi, Mid: Integer;
  Cmp: Integer;
begin
  Result := tOther;
  Cdata := cdNone;
  CdataName := nil;
  CdataLen := 0;
  L := 0;
  I := 0;
  while I < Len do
  begin
    if L >= MAX_TAG then Exit;
    if P[I] < $80 then
    begin
      Name[L] := LowerAscii(P[I]);
      Inc(I);
    end
    else if (I + 2 < Len) and (P[I] = $E2) and (P[I + 1] = $84) and (P[I + 2] = $AA) then
    begin
      Name[L] := Ord('k');   { KELVIN SIGN }
      Inc(I, 3);
    end
    else
      Exit;   { no other character lowers to ASCII alone }
    Inc(L);
  end;
  Lo := Low(KNOWN_TAGS);
  Hi := High(KNOWN_TAGS);
  while Lo <= Hi do
  begin
    Mid := (Lo + Hi) div 2;
    M := Length(KNOWN_TAGS[Mid].Name);
    if L < M then M := L;
    Cmp := CompareByte(Name[0], KNOWN_TAGS[Mid].Name[1], M);
    if Cmp = 0 then Cmp := Integer(L) - Length(KNOWN_TAGS[Mid].Name);
    if Cmp = 0 then
    begin
      Cdata := KNOWN_TAGS[Mid].Cdata;
      if Cdata in [cdRaw, cdEscapable] then
      begin
        CdataName := @KNOWN_TAGS[Mid].Name[1];
        CdataLen := Length(KNOWN_TAGS[Mid].Name);
      end;
      Exit(KNOWN_TAGS[Mid].Tag);
    end;
    if Cmp < 0 then Hi := Mid - 1 else Lo := Mid + 1;
  end;
end;

function AttrOf(P: PByte; Len: PtrUInt): TAttr;
var Name: array[0..6] of Byte; I: PtrUInt;
begin
  Result := aOther;
  if (Len < 3) or (Len > 7) then Exit;
  for I := 0 to Len - 1 do Name[I] := LowerAscii(P[I]);
  if SameBytes(@Name[0], Len, 'href') then Result := aHref
  else if SameBytes(@Name[0], Len, 'alt') then Result := aAlt
  else if SameBytes(@Name[0], Len, 'caption') then Result := aCaption
  else if SameBytes(@Name[0], Len, 'sgid') then Result := aSgid;
end;

{ A value decoded into the Scratch (not kept: ScratchTop stays): its length,
  0 without one }
function AttrText(var S: TState; const A: TAttrValue): PtrUInt;
begin
  if not (A.Seen and A.Has) or (A.Len = 0) then Exit(0);
  Result := UnescapeAttr(S, A.At, A.At + A.Len);
end;

procedure EmitBracketed(var S: TState; P: PByte; L: PtrUInt);
begin
  Emit(S, Ord('['));
  EmitBytes(S, P, L);
  Emit(S, Ord(']'));
end;

procedure Attachment(var S: TState; const Attrs: TAttrs);
var L, SLen, FAt, FLen: PtrUInt; K: PtrInt; R: PInt64; Sgid: PByte; Found: Boolean;
begin
  L := AttrText(S, Attrs[aAlt]);
  if L = 0 then L := AttrText(S, Attrs[aCaption]);
  if L > 0 then
  begin
    if not S.Overflow then EmitBracketed(S, S.Scratch + S.ScratchTop, L);
    Exit;
  end;
  SLen := AttrText(S, Attrs[aSgid]);
  if S.Overflow then Exit;
  Sgid := S.Scratch + S.ScratchTop;
  Found := False;
  FAt := 0;
  FLen := 0;
  for K := 0 to S.NameCount - 1 do
  begin
    R := @S.NameRecs[K * NAME_WORDS];
    if (PtrUInt(R[1]) = SLen) and ((SLen = 0) or (CompareByte(S.Names[R[0]], Sgid^, SLen) = 0)) then
    begin
      Found := True;
      FAt := R[2];
      FLen := R[3];
      Break;
    end;
  end;
  if Found and (FLen > 0) then EmitBracketed(S, S.Names + FAt, FLen)
  else EmitStr(S, '[file]');
end;

procedure LinkStart(var S: TState; const Attrs: TAttrs);
var R: PInt64; L: PtrUInt;
begin
  if S.LinkCount >= S.LinksCap then
  begin
    S.Overflow := True;
    Exit;
  end;
  R := @S.Links[S.LinkCount * LINK_WORDS];
  Inc(S.LinkCount);
  R[0] := S.ScratchTop;
  R[1] := -1;
  R[2] := S.N;
  if Attrs[aHref].Seen and Attrs[aHref].Has then
  begin
    if Attrs[aHref].Len > 0 then L := UnescapeAttr(S, Attrs[aHref].At,
      Attrs[aHref].At + Attrs[aHref].Len)
    else L := 0;
    R[1] := L;
    Inc(S.ScratchTop, L);
  end;
end;

procedure LinkEnd(var S: TState);
var R: PInt64; From, To_: PtrUInt; Href: PByte; HLen: PtrUInt;
begin
  if S.LinkCount = 0 then Exit;
  Dec(S.LinkCount);
  R := @S.Links[S.LinkCount * LINK_WORDS];
  S.ScratchTop := R[0];
  if (R[1] <= 0) or S.Overflow then Exit;
  Href := S.Scratch + R[0];
  HLen := R[1];
  { the link's text, without the spaces around it }
  From := R[2];
  To_ := S.N;
  while (From < To_) and IsHtmlSpace(S.Out_[From]) do Inc(From);
  while (To_ > From) and IsHtmlSpace(S.Out_[To_ - 1]) do Dec(To_);
  if (To_ - From = HLen) and (CompareByte(S.Out_[From], Href^, HLen) = 0) then Exit;
  Emit(S, SP);
  Emit(S, Ord('('));
  EmitBytes(S, Href, HLen);
  Emit(S, Ord(')'));
end;

procedure StartTag(var S: TState; Tag: TTag; const Attrs: TAttrs);
var L: PtrUInt;
begin
  S.AfterPre := False;
  if Tag = tSkip then
  begin
    Inc(S.Skip);
    Exit;
  end;
  if S.Skip > 0 then Exit;
  case Tag of
    tBlock: Block(S);
    tBr: Br(S);
    tLi:
      begin
        Line(S);
        Flush(S);
        Put(S, Ord('-'));
        S.PendingSpace := True;
      end;
    tHr:
      begin
        Line(S);
        for L := 1 to HR_WIDTH do Emit(S, Ord('-'));
        Line(S);
      end;
    tPre:
      begin
        Block(S);
        EmitStr(S, '```');
        Line(S);
        Inc(S.PreDepth);
        S.AfterPre := True;
      end;
    tCode: if S.PreDepth = 0 then TextByte(S, Ord('`'));
    tImg:
      begin
        L := AttrText(S, Attrs[aAlt]);
        if (L > 0) and not S.Overflow then EmitBracketed(S, S.Scratch + S.ScratchTop, L);
      end;
    tAttachment: Attachment(S, Attrs);
    tA: LinkStart(S, Attrs);
  end;
end;

procedure EndTag(var S: TState; Tag: TTag);
begin
  S.AfterPre := False;
  if Tag = tSkip then
  begin
    if S.Skip > 0 then Dec(S.Skip);
    Exit;
  end;
  if S.Skip > 0 then Exit;
  case Tag of
    tBlock: Block(S);
    tLi: Line(S);
    tPre:
      if S.PreDepth > 0 then
      begin
        Dec(S.PreDepth);
        Line(S);
        EmitStr(S, '```');
        Block(S);
      end
      else
        Block(S);
    tCode: if S.PreDepth = 0 then TextByte(S, Ord('`'));
    tA: LinkEnd(S);
  end;
end;

{ Text between the markup: decoded, unless it's raw text }
procedure Data(var S: TState; From, To_: PtrUInt; Escapable: Boolean);
var Drop: Boolean;
begin
  Drop := S.AfterPre;
  S.AfterPre := False;
  if S.Skip > 0 then Exit;
  S.DropNl := Drop;
  if Escapable then EmitUnescaped(S, S.Html, From, To_)
  else EmitBytes(S, S.Html + From, To_ - From);
  S.DropNl := False;
end;

{ ------------------------------------------------------------- the parser }

const
  { [\t\n\r\f ] and [\t\n\r\f /] }
  WS_SLASH: set of Byte = [TAB, LF, FF, CR, SP, Ord('/')];
  WS: set of Byte = [TAB, LF, FF, CR, SP];
  NAME_STOP: set of Byte = [TAB, LF, FF, CR, SP, Ord('/'), Ord('>')];
  ATTR_STOP: set of Byte = [TAB, LF, FF, CR, SP, Ord('/'), Ord('='), Ord('>')];
  BARE_STOP: set of Byte = [TAB, LF, FF, CR, SP, Ord('>')];
  LOOKBEHIND: set of Byte = [TAB, LF, FF, CR, SP, Ord('/'), Ord(''''), Ord('"')];

{ The value group of attrfind/locatetagend from P (right after the name):
  `[\t\n\r\f ]*=[\t\n\r\f ]*('[^']*'|"[^"]*"|(?!['"])[^>\t\n\r\f ]*)`.
  True when it matches: P is then its end, and Value the value. }
function ValueGroup(var S: TState; var P: PtrUInt; out VAt, VLen: PtrUInt): Boolean;
var Q, Q0, C: PtrUInt; H: PByte; N: PtrUInt; Close: PtrInt;
begin
  Result := False;
  H := S.Html;
  N := S.Len;
  Q := P;
  while (Q < N) and (H[Q] in WS) do Inc(Q);
  if (Q >= N) or (H[Q] <> Ord('=')) then Exit;
  Inc(Q);
  Q0 := Q;
  while (Q < N) and (H[Q] in WS) do Inc(Q);
  if (Q < N) and ((H[Q] = Ord('''')) or (H[Q] = Ord('"'))) then
  begin
    Close := FindByte(H, Q + 1, N, H[Q]);
    if Close >= 0 then
    begin
      { quoted: the value is what is between the quotes }
      VAt := Q + 1;
      VLen := Close - Q - 1;
      P := Close + 1;
      Exit(True);
    end;
    { unclosed: the regex gives back a space, if there is one, for an empty
      bare value }
    if Q > Q0 then
    begin
      VAt := Q - 1;
      VLen := 0;
      P := Q - 1;
      Exit(True);
    end;
    Exit(False);
  end;
  C := Q;
  while (C < N) and not (H[C] in BARE_STOP) do Inc(C);
  VAt := Q;
  VLen := C - Q;
  P := C;
  Result := True;
end;

{ locatetagend from P (the first letter of the name): the end of the tag }
function LocateTagEnd(var S: TState; P: PtrUInt): PtrUInt;
var H: PByte; N, VAt, VLen: PtrUInt;
begin
  H := S.Html;
  N := S.Len;
  Inc(P);
  while (P < N) and not (H[P] in NAME_STOP) do Inc(P);
  while (P < N) and (H[P] in WS_SLASH) do Inc(P);
  while (P < N) and (H[P - 1] in LOOKBEHIND) and not (H[P] in NAME_STOP) do
  begin
    Inc(P);
    while (P < N) and not (H[P] in ATTR_STOP) do Inc(P);
    ValueGroup(S, P, VAt, VLen);
    while (P < N) and (H[P] in WS_SLASH) do Inc(P);
  end;
  if (P < N) and (H[P] = Ord('>')) then Inc(P);
  Result := P;
end;

{ `(?:[\t\n\r\f ]|/(?!>))*` from P }
procedure SkipTagSpace(var S: TState; var P: PtrUInt);
begin
  while P < S.Len do
    if S.Html[P] in WS then Inc(P)
    else if (S.Html[P] = Ord('/')) and not ((P + 1 < S.Len) and (S.Html[P + 1] = Ord('>'))) then
      Inc(P)
    else
      Break;
end;

{ The end of the name of a tag from P (its first letter): tagfind_tolerant }
function TagNameEnd(var S: TState; P: PtrUInt): PtrUInt;
begin
  Inc(P);
  while (P < S.Len) and not (S.Html[P] in NAME_STOP) do Inc(P);
  Result := P;
end;

{ What is left of a start tag, K to E, stripped: ">" or "/>" }
function Closes(var S: TState; K, E: PtrUInt; out SelfClosing: Boolean): Boolean;
var A, B, Z, L: PtrUInt;
begin
  SelfClosing := False;
  if K >= E then Exit(False);
  A := K;
  B := K;
  Z := K;
  { strip as str.strip() does }
  while Z < E do
  begin
    L := PySpaceLen(S.Html + Z, E - Z);
    if L = 0 then
    begin
      if B = K then A := Z;
      Inc(Z, CharLen(S.Html + Z, E - Z));
      B := Z;
    end
    else
      Inc(Z, L);
  end;
  if B = K then Exit(False);   { only spaces }
  if (B - A = 1) and (S.Html[A] = Ord('>')) then Exit(True);
  if (B - A = 2) and (S.Html[A] = Ord('/')) and (S.Html[A + 1] = Ord('>')) then
  begin
    SelfClosing := True;
    Exit(True);
  end;
  Result := False;
end;

{ parse_starttag at I ("<" and a letter): the end, or -1 }
function StartTagAt(var S: TState; I: PtrUInt): PtrInt;
var
  H: PByte; E, K, NameEnd, NAt, NLen, VAt, VLen, P: PtrUInt; Has, SelfClosing: Boolean;
  Attrs: TAttrs; A: TAttr; Tag: TTag; Cdata: TCdata; CdataName: PChar; CdataLen: PtrUInt;
begin
  H := S.Html;
  E := LocateTagEnd(S, I + 1);
  if H[E - 1] <> Ord('>') then Exit(-1);
  NameEnd := TagNameEnd(S, I + 1);
  K := NameEnd;
  SkipTagSpace(S, K);
  FillChar(Attrs, SizeOf(Attrs), 0);
  while K < E do
  begin
    { attrfind_tolerant at K }
    if (K >= S.Len) or not (H[K - 1] in LOOKBEHIND) or (H[K] in NAME_STOP) then Break;
    NAt := K;
    P := K + 1;
    while (P < S.Len) and not (H[P] in ATTR_STOP) do Inc(P);
    NLen := P - NAt;
    Has := ValueGroup(S, P, VAt, VLen);
    SkipTagSpace(S, P);
    A := AttrOf(H + NAt, NLen);
    if (A <> aOther) and not Attrs[A].Seen then
    begin
      Attrs[A].Seen := True;
      Attrs[A].Has := Has;
      Attrs[A].At := VAt;
      Attrs[A].Len := VLen;
    end;
    K := P;
  end;
  if not Closes(S, K, E, SelfClosing) then
  begin
    Data(S, I, E, False);
    Exit(E);
  end;
  Tag := TagOf(H + I + 1, NameEnd - I - 1, Cdata, CdataName, CdataLen);
  StartTag(S, Tag, Attrs);
  if SelfClosing then
    EndTag(S, Tag)
  else if Cdata <> cdNone then
  begin
    S.Cdata := Cdata;
    S.CdataName := CdataName;
    S.CdataLen := CdataLen;
  end;
  Result := E;
end;

{ parse_endtag at I ("</"): the end, or -1 }
function EndTagAt(var S: TState; I: PtrUInt): PtrInt;
var H: PByte; E, NameEnd, CdataLen: PtrUInt; Gt: PtrInt; Cdata: TCdata; CdataName: PChar;
begin
  H := S.Html;
  Gt := FindByte(H, I + 2, S.Len, Ord('>'));
  if Gt < 0 then Exit(-1);
  if not IsLetter(H[I + 2]) then
  begin
    if H[I + 2] = Ord('>') then Exit(I + 3);   { "</>" }
    Exit(Gt + 1);                               { a bogus comment }
  end;
  E := LocateTagEnd(S, I + 2);
  if H[E - 1] <> Ord('>') then Exit(-1);
  NameEnd := TagNameEnd(S, I + 2);
  EndTag(S, TagOf(H + I + 2, NameEnd - I - 2, Cdata, CdataName, CdataLen));
  S.Cdata := cdNone;
  Result := E;
end;

{ <!--: the end of the comment, or -1 }
function CommentAt(var S: TState; I: PtrUInt): PtrInt;
var H: PByte; P, N: PtrUInt;
begin
  H := S.Html;
  N := S.Len;
  P := I + 4;
  if (P < N) and (H[P] = Ord('>')) then Exit(P + 1);
  if (P + 1 < N) and (H[P] = Ord('-')) and (H[P + 1] = Ord('>')) then Exit(P + 2);
  while P + 2 < N do
  begin
    if (H[P] = Ord('-')) and (H[P + 1] = Ord('-')) then
    begin
      if H[P + 2] = Ord('>') then Exit(P + 3);
      if (H[P + 2] = Ord('!')) and (P + 3 < N) and (H[P + 3] = Ord('>')) then Exit(P + 4);
    end;
    Inc(P);
  end;
  Result := -1;
end;

{ <!: the end of the declaration, or -1 }
function DeclarationAt(var S: TState; I: PtrUInt): PtrInt;
const CDATA_OPEN = '<![CDATA[';
var H: PByte; P, N: PtrUInt; Gt: PtrInt;
begin
  H := S.Html;
  N := S.Len;
  if (I + 9 <= N) and SameBytes(H + I, 9, CDATA_OPEN) then
  begin
    P := I + 9;
    while P + 2 < N do
    begin
      if (H[P] = Ord(']')) and (H[P + 1] = Ord(']')) and (H[P + 2] = Ord('>')) then Exit(P + 3);
      Inc(P);
    end;
    Exit(-1);
  end;
  { <!doctype ...> and a bogus comment both end at the first ">" }
  Gt := FindByte(H, I + 2, N, Ord('>'));
  if Gt < 0 then Result := -1 else Result := Gt + 1;
end;

{ Where the raw text of the cdata element ends: "</name" (ASCII, any case)
  and one of [\t\n\r\f />], from I, or -1 }
function CdataEnd(var S: TState; I: PtrUInt): PtrInt;
var H: PByte; N, L, K: PtrUInt; Lt: PtrInt; Ok: Boolean;
begin
  H := S.Html;
  N := S.Len;
  L := S.CdataLen;
  while True do
  begin
    Lt := FindByte(H, I, N, Ord('<'));
    if Lt < 0 then Exit(-1);
    if (PtrUInt(Lt) + 2 + L < N) and (H[Lt + 1] = Ord('/')) then
    begin
      Ok := True;
      for K := 0 to L - 1 do
        if LowerAscii(H[Lt + 2 + K]) <> Ord(S.CdataName[K]) then
        begin
          Ok := False;
          Break;
        end;
      if Ok and (H[Lt + 2 + L] in NAME_STOP) then Exit(Lt);
    end;
    I := Lt + 1;
  end;
end;

function Html2Text(Html: PByte; Len: PtrUInt; Names: PByte; NameRecs: PInt64;
  NameCount: PtrInt; Out_: PByte; Cap: PtrUInt; Scratch: PByte; ScratchCap: PtrUInt;
  Links: PInt64; LinksCap: PtrInt): Int64;
var S: TState; I, J: PtrUInt; K, Found: PtrInt; Rest: Boolean; H: PByte;
begin
  FillChar(S, SizeOf(S), 0);
  S.Html := Html;
  S.Len := Len;
  S.Out_ := Out_;
  S.Cap := Cap;
  S.Scratch := Scratch;
  S.ScratchCap := ScratchCap;
  S.Links := Links;
  S.LinksCap := LinksCap;
  S.Names := Names;
  S.NameRecs := NameRecs;
  S.NameCount := NameCount;
  H := Html;
  I := 0;
  Rest := False;   { a cdata element that isn't closed: the rest is its text }
  while I < Len do
  begin
    case S.Cdata of
      cdNone:
        begin
          Found := FindByte(H, I, Len, Ord('<'));
          if Found < 0 then J := Len else J := Found;
        end;
      cdPlaintext: J := Len;
    else
      Found := CdataEnd(S, I);
      if Found < 0 then
      begin
        Rest := True;
        Break;
      end;
      J := Found;
    end;
    if I < J then Data(S, I, J, S.Cdata in [cdNone, cdEscapable]);
    I := J;
    if I >= Len then Break;
    { at "<" }
    if (I + 1 < Len) and IsLetter(H[I + 1]) then
      K := StartTagAt(S, I)
    else if (I + 1 < Len) and (H[I + 1] = Ord('/')) then
      K := EndTagAt(S, I)
    else if (I + 3 < Len) and (H[I + 1] = Ord('!')) and (H[I + 2] = Ord('-')) and
      (H[I + 3] = Ord('-')) then
      K := CommentAt(S, I)
    else if (I + 1 < Len) and (H[I + 1] = Ord('?')) then
    begin
      K := FindByte(H, I + 2, Len, Ord('>'));
      if K >= 0 then Inc(K);
    end
    else if (I + 1 < Len) and (H[I + 1] = Ord('!')) then
      K := DeclarationAt(S, I)
    else
    begin
      Data(S, I, I + 1, False);   { a "<" that starts nothing }
      K := I + 1;
    end;
    if K < 0 then
    begin
      { not closed when the HTML ends: dropped, except a "</" at the end }
      if (I + 2 = Len) and (H[I + 1] = Ord('/')) then Data(S, I, Len, False);
      K := Len;
    end;
    I := K;
  end;
  if Rest and (I < Len) then Data(S, I, Len, S.Cdata = cdEscapable);
  if S.Overflow then Exit(TOO_SMALL);
  Result := S.N;
end;

end.
