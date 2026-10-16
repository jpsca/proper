{ proper_native - Proper's native code, loaded by proper/_native with cffi
  (proper_native.h declares it).

  Signed tokens. proper_sign signs a payload and proper_unsign checks a
  token and gives its payload back, in the format of itsdangerous (its
  URLSafeTimedSerializer and URLSafeSerializer with HMAC key derivation and
  SHA-256), so tokens and session cookies made before keep working:

    timed:    payload "." base64url(timestamp) "." base64url(HMAC-SHA256)
    untimed:  payload "." base64url(HMAC-SHA256)

  payload is base64url (no padding) of the JSON, or "." + base64url of its
  zlib compression; the timestamp is the signing time in Unix seconds,
  big-endian, leading zero bytes dropped. Python makes the payload (JSON
  and zlib, as itsdangerous does) and decodes the JSON that proper_unsign
  writes; this library does the timestamp, the HMAC, the base64 and the
  zlib decompression. The HMAC keys are derived by Python (HMAC-SHA256 of
  the salt with the secret key) and prepared here once (proper_hmac_key).

  SHA-256 is the block compression of HashLib4Pascal's kernels
  (sha256/proper_sha256.pas: SHA-NI or AVX2 on x86-64, the crypto
  extensions on ARM64, else scalar code, chosen once when the library
  loads). HMAC (RFC 2104) is computed from the two hash states after the
  first block of key xor ipad and key xor opad. zlib is the system's
  libz.so.1, loaded when the library loads.

  Threading. Python calls these functions from its own threads, which Free
  Pascal did not create: they use no managed strings, no exceptions and no
  Free Pascal heap, only the stack and the buffers the caller passes. }
library proper_native;

{$mode objfpc}{$H+}
{$R-}{$Q-}{$PointerMath On}

uses
  cthreads, dynlibs, proper_sha256;

const
  VERSION = '0.1.0';
  { 9999-12-31 23:59:59 UTC, the last second a `datetime` holds }
  LAST_TIMESTAMP = 253402300799;
  { what proper_unsign and proper_sign return instead of a length }
  BAD_SIGNATURE = -1;   { no signature, or none of the keys made it }
  EXPIRED = -2;         { older than max_age, or signed in the future }
  MALFORMED = -3;       { a good signature over a bad timestamp or payload }
  TOO_SMALL = -4;       { the output or scratch buffer is too small }
  Z_BUF_ERROR = -5;

type
  TSha256State = array[0..7] of UInt32;
  TSha256Digest = array[0..31] of Byte;
  { HMAC-SHA256 key: the states after one block of key xor ipad and opad }
  THmacKey = record
    Inner, Outer: TSha256State;
  end;
  PHmacKey = ^THmacKey;
  { zlib's uncompress(dest, destLen, source, sourceLen) }
  TUncompress = function(Dest: PByte; DestLen: PPtrUInt; Source: PByte;
    SourceLen: PtrUInt): LongInt; cdecl;

const
  SHA256_IV: TSha256State = (
    $6a09e667, $bb67ae85, $3c6ef372, $a54ff53a,
    $510e527f, $9b05688c, $1f83d9ab, $5be0cd19);

var
  LibZ: TLibHandle = NilHandle;
  Uncompress: TUncompress = nil;

{ ------------------------------------------------------------- SHA-256 }

{ Hashes Len bytes after Prefix bytes already compressed into St, and
  writes the digest. }
procedure Sha256Finish(var St: TSha256State; Prefix: QWord; P: PByte; Len: PtrUInt;
  out D: TSha256Digest);
var Block: array[0..127] of Byte; Full, Rest, Total, I: PtrUInt; Bits: QWord;
begin
  Full := Len div 64;
  if Full > 0 then SHA256_Compress(@St[0], P, Full);
  Rest := Len - Full * 64;
  FillChar(Block, SizeOf(Block), 0);
  if Rest > 0 then Move(P[Full * 64], Block[0], Rest);
  Block[Rest] := $80;
  if Rest >= 56 then Total := 128 else Total := 64;
  Bits := (Prefix + Len) * 8;
  for I := 0 to 7 do
    Block[Total - 1 - I] := Byte(Bits shr (8 * I));
  SHA256_Compress(@St[0], @Block[0], Total div 64);
  for I := 0 to 7 do
  begin
    D[I * 4] := Byte(St[I] shr 24);
    D[I * 4 + 1] := Byte(St[I] shr 16);
    D[I * 4 + 2] := Byte(St[I] shr 8);
    D[I * 4 + 3] := Byte(St[I]);
  end;
end;

procedure HmacSign(const K: THmacKey; P: PByte; Len: PtrUInt; out D: TSha256Digest);
var St: TSha256State; Inner: TSha256Digest;
begin
  St := K.Inner;
  Sha256Finish(St, 64, P, Len, Inner);
  St := K.Outer;
  Sha256Finish(St, 64, @Inner[0], 32, D);
end;

function ConstTimeEqual(A, B: PByte; Len: PtrUInt): Boolean;
var I: PtrUInt; Acc: Byte;
begin
  Acc := 0;
  for I := 0 to Len - 1 do
    Acc := Acc or (A[I] xor B[I]);
  Result := Acc = 0;
end;

{ -------------------------------------------------------------- base64 }

function B64Val(C: Byte): Integer; inline;
begin
  case Chr(C) of
    'A'..'Z': Result := C - Ord('A');
    'a'..'z': Result := C - Ord('a') + 26;
    '0'..'9': Result := C - Ord('0') + 52;
    '+', '-': Result := 62;
    '/', '_': Result := 63;
  else
    Result := -1;
  end;
end;

{ base64url without padding, decoded as Python's urlsafe_b64decode does after
  itsdangerous pads it with "=" (the lenient decoder of Lima's lima.crypto):
  characters outside the alphabet are skipped. False when it is not valid
  or does not fit in Cap bytes. }
function Base64Decode(Src: PByte; SrcLen: PtrUInt; Dst: PByte; Cap: PtrUInt;
  out DstLen: PtrUInt): Boolean;
var I: PtrUInt; QuadPos, Pads, V, Left: Integer;
begin
  DstLen := 0;
  QuadPos := 0;
  Pads := 0;
  Left := 0;
  Result := False;
  if SrcLen > 0 then
    for I := 0 to SrcLen - 1 do
    begin
      if Src[I] = Ord('=') then
      begin
        Inc(Pads);
        Continue;
      end;
      V := B64Val(Src[I]);
      if V < 0 then Continue;
      Pads := 0;
      if QuadPos = 0 then
      begin
        Left := V;
        QuadPos := 1;
        Continue;
      end;
      if DstLen >= Cap then Exit;
      case QuadPos of
        1: begin Dst[DstLen] := Byte((Left shl 2) or (V shr 4)); Left := V and $0F; end;
        2: begin Dst[DstLen] := Byte((Left shl 4) or (V shr 2)); Left := V and $03; end;
        3: Dst[DstLen] := Byte((Left shl 6) or V);
      end;
      Inc(DstLen);
      QuadPos := (QuadPos + 1) and 3;
    end;
  Inc(Pads, (4 - Integer(SrcLen mod 4)) mod 4);  { the padding itsdangerous adds }
  Result := (QuadPos = 0) or ((QuadPos >= 2) and (QuadPos + Pads >= 4));
end;

const
  B64: array[0..63] of Char =
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';

{ base64url of Src without padding, at Dst; returns its length. }
function Base64Encode(Src: PByte; SrcLen: PtrUInt; Dst: PByte): PtrUInt;
var I: PtrUInt; V: UInt32;
begin
  Result := 0;
  I := 0;
  while I + 3 <= SrcLen do
  begin
    V := (UInt32(Src[I]) shl 16) or (UInt32(Src[I + 1]) shl 8) or Src[I + 2];
    Dst[Result] := Ord(B64[V shr 18]);
    Dst[Result + 1] := Ord(B64[(V shr 12) and 63]);
    Dst[Result + 2] := Ord(B64[(V shr 6) and 63]);
    Dst[Result + 3] := Ord(B64[V and 63]);
    Inc(Result, 4);
    Inc(I, 3);
  end;
  case SrcLen - I of
    1:
      begin
        V := UInt32(Src[I]) shl 16;
        Dst[Result] := Ord(B64[V shr 18]);
        Dst[Result + 1] := Ord(B64[(V shr 12) and 63]);
        Inc(Result, 2);
      end;
    2:
      begin
        V := (UInt32(Src[I]) shl 16) or (UInt32(Src[I + 1]) shl 8);
        Dst[Result] := Ord(B64[V shr 18]);
        Dst[Result + 1] := Ord(B64[(V shr 12) and 63]);
        Dst[Result + 2] := Ord(B64[(V shr 6) and 63]);
        Inc(Result, 3);
      end;
  end;
end;

function LastDot(P: PByte; Len: PtrUInt): PtrInt;
begin
  Result := PtrInt(Len) - 1;
  while (Result >= 0) and (P[Result] <> Ord('.')) do Dec(Result);
end;

{ ------------------------------------------------------------- exports }

function proper_native_version: PChar; cdecl;
begin
  Result := VERSION;
end;

function proper_hmac_key_size: PtrUInt; cdecl;
begin
  Result := SizeOf(THmacKey);
end;

{ Prepares an HMAC-SHA256 key of at most 64 bytes into Out
  (proper_hmac_key_size bytes). 0 ok, -1 a longer key. }
function proper_hmac_key(Key: PByte; Len: PtrUInt; Out_: PHmacKey): LongInt; cdecl;
var IPad, OPad: array[0..63] of Byte; I: Integer;
begin
  if Len > 64 then Exit(-1);
  FillChar(IPad, SizeOf(IPad), 0);
  if Len > 0 then Move(Key^, IPad[0], Len);
  OPad := IPad;
  for I := 0 to 63 do
  begin
    IPad[I] := IPad[I] xor $36;
    OPad[I] := OPad[I] xor $5C;
  end;
  Out_^.Inner := SHA256_IV;
  SHA256_Compress(@Out_^.Inner[0], @IPad[0], 1);
  Out_^.Outer := SHA256_IV;
  SHA256_Compress(@Out_^.Outer[0], @OPad[0], 1);
  Result := 0;
end;

{ SHA-256 of a whole message, and the kernel: for the tests, which check
  every kernel this CPU has against Python's hashlib. }
procedure proper_sha256(Msg: PByte; Len: PtrUInt; Digest: PByte); cdecl;
var St: TSha256State; D: TSha256Digest;
begin
  St := SHA256_IV;
  Sha256Finish(St, 0, Msg, Len, D);
  Move(D[0], Digest^, 32);
end;

{ 0 scalar, 1 AVX2, 2 SHA-NI, 3 ARM crypto extensions }
function proper_sha256_kernel: LongInt; cdecl;
begin
  Result := Ord(Sha256Kernel);
end;

{ Switches to a kernel: 1 done, 0 not on this CPU. Tests only, with no
  other thread hashing. }
function proper_sha256_use(Kernel: LongInt): LongInt; cdecl;
begin
  Result := 0;
  if (Kernel >= Ord(Low(TSha256Kernel))) and (Kernel <= Ord(High(TSha256Kernel))) then
    Result := Ord(Sha256UseKernel(TSha256Kernel(Kernel)));
end;

procedure proper_hmac_sha256(Key: PHmacKey; Msg: PByte; Len: PtrUInt; Digest: PByte); cdecl;
var D: TSha256Digest;
begin
  HmacSign(Key^, Msg, Len, D);
  Move(D[0], Digest^, 32);
end;

{ Decodes a payload (base64url, after a "." zlib too) into Out: its length,
  MALFORMED or TOO_SMALL. }
function DecodePayload(P: PByte; Len: PtrUInt; Out_: PByte; Cap: PtrUInt; Scratch: PByte;
  ScratchCap: PtrUInt): Int64;
var N, Size: PtrUInt; R: LongInt;
begin
  if (Len > 0) and (P[0] = Ord('.')) then
  begin
    if Len - 1 > ScratchCap then Exit(TOO_SMALL);
    if not Base64Decode(@P[1], Len - 1, Scratch, ScratchCap, N) then Exit(MALFORMED);
    if not Assigned(Uncompress) then Exit(MALFORMED);
    Size := Cap;
    R := Uncompress(Out_, @Size, Scratch, N);
    if R = Z_BUF_ERROR then
    begin
      { zlib says "buffer error" for a stream cut short too: with an output
        buffer larger than everything a stream of N bytes can inflate to
        (1032 times N, zlib's limit), it is the stream }
      if Cap > N * 1032 then Exit(MALFORMED);
      Exit(TOO_SMALL);
    end;
    if R <> 0 then Exit(MALFORMED);
    Exit(Size);
  end;
  if Len > Cap then Exit(TOO_SMALL);
  if not Base64Decode(P, Len, Out_, Cap, N) then Exit(MALFORMED);
  Result := N;
end;

{ The payload of a token, written to Out (Cap bytes; a compressed payload is
  base64-decoded into Scratch first): its length, or BAD_SIGNATURE, EXPIRED,
  MALFORMED or TOO_SMALL (call again with larger buffers). Keys: Count
  prepared keys, tried in order. Timed: 1 for a timed token, whose
  timestamp goes to Ts; MaxAge < 0 is no age limit. An untimed token whose
  payload has a "." after its first character is MALFORMED: it is a timed
  token, whose signature covers the payload and the timestamp, so it would
  otherwise read as untimed (URLSafeSerializer does) and never expire. }
function proper_unsign(Keys: PHmacKey; Count, Timed: LongInt; Token: PByte; Len: PtrUInt;
  Now, MaxAge: Int64; Out_: PByte; Cap: PtrUInt; Scratch: PByte; ScratchCap: PtrUInt;
  Ts: PInt64): Int64; cdecl;
var
  SigAt, TsAt, I: PtrInt;
  Sig: array[0..47] of Byte;
  TsBytes: array[0..15] of Byte;
  D: TSha256Digest;
  N: PtrUInt;
  T: QWord;
  Age: Int64;
  Good: Boolean;
begin
  Ts^ := 0;
  SigAt := LastDot(Token, Len);
  if (SigAt < 0) or (Len - PtrUInt(SigAt) - 1 > 64) then Exit(BAD_SIGNATURE);
  if not Base64Decode(@Token[SigAt + 1], Len - PtrUInt(SigAt) - 1, @Sig[0], SizeOf(Sig), N)
    or (N <> 32) then Exit(BAD_SIGNATURE);
  Good := False;
  for I := 0 to Count - 1 do
  begin
    HmacSign(Keys[I], Token, PtrUInt(SigAt), D);
    if ConstTimeEqual(@D[0], @Sig[0], 32) then
    begin
      Good := True;
      Break;
    end;
  end;
  if not Good then Exit(BAD_SIGNATURE);

  if Timed = 0 then
  begin
    for I := 1 to SigAt - 1 do
      if Token[I] = Ord('.') then Exit(MALFORMED);
    Exit(DecodePayload(Token, PtrUInt(SigAt), Out_, Cap, Scratch, ScratchCap));
  end;

  TsAt := LastDot(Token, PtrUInt(SigAt));
  if (TsAt < 0) or (SigAt - TsAt - 1 > 12) then Exit(MALFORMED);
  if not Base64Decode(@Token[TsAt + 1], PtrUInt(SigAt - TsAt - 1), @TsBytes[0],
    SizeOf(TsBytes), N) or (N > 8) then Exit(MALFORMED);
  T := 0;
  for I := 0 to PtrInt(N) - 1 do T := (T shl 8) or TsBytes[I];
  if T > LAST_TIMESTAMP then Exit(MALFORMED);
  Ts^ := Int64(T);
  if MaxAge >= 0 then
  begin
    Age := Now - Int64(T);
    if (Age > MaxAge) or (Age < 0) then Exit(EXPIRED);
  end;
  Result := DecodePayload(Token, PtrUInt(TsAt), Out_, Cap, Scratch, ScratchCap);
end;

{ Signs a payload with a prepared key into Out (Cap bytes, at least
  Len + 58): the token's length, or TOO_SMALL. Timestamp < 0: an untimed
  token. }
function proper_sign(Key: PHmacKey; Payload: PByte; Len: PtrUInt; Timestamp: Int64;
  Out_: PByte; Cap: PtrUInt): Int64; cdecl;
var N, I: PtrUInt; TsBytes: array[0..7] of Byte; T: QWord; D: TSha256Digest;
begin
  if Cap < Len + 58 then Exit(TOO_SMALL);
  if Len > 0 then Move(Payload^, Out_^, Len);
  N := Len;
  if Timestamp >= 0 then
  begin
    { big-endian, leading zero bytes dropped (0 gives none) }
    T := QWord(Timestamp);
    I := 0;
    while T > 0 do
    begin
      TsBytes[7 - I] := Byte(T);
      T := T shr 8;
      Inc(I);
    end;
    Out_[N] := Ord('.');
    Inc(N);
    Inc(N, Base64Encode(@TsBytes[8 - I], I, @Out_[N]));
  end;
  HmacSign(Key^, Out_, N, D);
  Out_[N] := Ord('.');
  Inc(N);
  Inc(N, Base64Encode(@D[0], 32, @Out_[N]));
  Result := N;
end;

exports
  proper_native_version,
  proper_hmac_key_size,
  proper_hmac_key,
  proper_hmac_sha256,
  proper_sha256,
  proper_sha256_kernel,
  proper_sha256_use,
  proper_sign,
  proper_unsign;

initialization
  LibZ := LoadLibrary('libz.so.1');
  if LibZ <> NilHandle then
    Uncompress := TUncompress(GetProcedureAddress(LibZ, 'uncompress'));

end.
