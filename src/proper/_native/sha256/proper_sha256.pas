{ proper_sha256 - SHA-256 block compression: the kernels of HashLib4Pascal
  (https://github.com/Xor-el/HashLib4Pascal, commit 8b2cd8d, MIT license in
  LICENSE; README.md lists what was taken and what changed).

  SHA256_Compress(State, Data, NumBlocks) hashes NumBlocks 64-byte blocks
  into the 8 words of State. It is the best kernel the running CPU has,
  chosen when the unit initializes:

  - x86-64: SHA-NI, else AVX2 (with BMI2), else the scalar code below;
  - ARM64: the SHA-256 crypto extensions, else the scalar code below.

  Padding and the digest are the caller's (proper_native). The kernels and
  the selection use no managed strings, no exceptions and no heap, so they
  may run on threads Free Pascal did not create. }
unit proper_sha256;

{$mode objfpc}{$H+}
{$R-}{$Q-}{$PointerMath On}
{$IFDEF CPUX86_64}
  {$ASMMODE INTEL}
  {$DEFINE HASHLIB_SYSV_X64_ABI}  { the kernels' prologues: Linux's ABI }
{$ENDIF}

interface

type
  TSha256CompressProc = procedure(AState, AData: Pointer; ANumBlocks: UInt32);
  TSha256Kernel = (skScalar, skAvx2, skShaNi, skCryptoExt);

var
  { The kernel in use; SHA256_Compress never changes after initialization
    unless Sha256UseKernel is called (tests). }
  SHA256_Compress: TSha256CompressProc;

{ The kernel SHA256_Compress is. }
function Sha256Kernel: TSha256Kernel;
{ Whether this CPU can run K. }
function Sha256HasKernel(K: TSha256Kernel): Boolean;
{ Switches to K if the CPU can run it (False otherwise): for tests, before
  any other thread hashes. }
function Sha256UseKernel(K: TSha256Kernel): Boolean;

implementation

{$IFDEF CPUAARCH64}
uses
  dynlibs;
{$ENDIF}

const
  // K256 round constants, from HashLib4Pascal's HlpSHA2_256Base.
  K256: array [0 .. 63] of UInt32 = (
    $428A2F98, $71374491, $B5C0FBCF, $E9B5DBA5,
    $3956C25B, $59F111F1, $923F82A4, $AB1C5ED5,
    $D807AA98, $12835B01, $243185BE, $550C7DC3,
    $72BE5D74, $80DEB1FE, $9BDC06A7, $C19BF174,
    $E49B69C1, $EFBE4786, $0FC19DC6, $240CA1CC,
    $2DE92C6F, $4A7484AA, $5CB0A9DC, $76F988DA,
    $983E5152, $A831C66D, $B00327C8, $BF597FC7,
    $C6E00BF3, $D5A79147, $06CA6351, $14292967,
    $27B70A85, $2E1B2138, $4D2C6DFC, $53380D13,
    $650A7354, $766A0ABB, $81C2C92E, $92722C85,
    $A2BFE8A1, $A81A664B, $C24B8B70, $C76C51A3,
    $D192E819, $D6990624, $F40E3585, $106AA070,
    $19A4C116, $1E376C08, $2748774C, $34B0BCB5,
    $391C0CB3, $4ED8AA4A, $5B9CCA4F, $682E6FF3,
    $748F82EE, $78A5636F, $84C87814, $8CC70208,
    $90BEFFFA, $A4506CEB, $BEF9A3F7, $C67178F2
  );

var
  Active: TSha256Kernel = skScalar;

{ ------------------------------------------------------------- scalar }

{ HashLib4Pascal's SHA256_Compress_Scalar, with the big-endian load and the
  rotations written out instead of TBinaryPrimitives and TBitOperations. }
procedure SHA256_Compress_Scalar(AState, AData: Pointer; ANumBlocks: UInt32);
var
  LPState: PCardinal;
  LPData: PByte;
  LA, LB, LC, LD, LE, LF, LG, LH, LT1, LT2: UInt32;
  LW: array [0 .. 63] of UInt32;
  LRound: Int32;
begin
  LPState := PCardinal(AState);
  LPData := PByte(AData);

  while ANumBlocks > 0 do
  begin
    for LRound := 0 to 15 do
      LW[LRound] := (UInt32(LPData[LRound * 4]) shl 24) or (UInt32(LPData[LRound * 4 + 1]) shl 16)
        or (UInt32(LPData[LRound * 4 + 2]) shl 8) or UInt32(LPData[LRound * 4 + 3]);

    for LRound := 16 to 63 do
    begin
      LT1 := LW[LRound - 2];
      LT2 := LW[LRound - 15];
      LW[LRound] := (RorDWord(LT1, 17) xor RorDWord(LT1, 19) xor (LT1 shr 10)) + LW[LRound - 7] +
        (RorDWord(LT2, 7) xor RorDWord(LT2, 18) xor (LT2 shr 3)) + LW[LRound - 16];
    end;

    LA := LPState[0]; LB := LPState[1]; LC := LPState[2]; LD := LPState[3];
    LE := LPState[4]; LF := LPState[5]; LG := LPState[6]; LH := LPState[7];

    for LRound := 0 to 63 do
    begin
      LT1 := LH + (RorDWord(LE, 6) xor RorDWord(LE, 11) xor RorDWord(LE, 25)) +
        ((LE and LF) xor (not LE and LG)) + K256[LRound] + LW[LRound];
      LT2 := (RorDWord(LA, 2) xor RorDWord(LA, 13) xor RorDWord(LA, 22)) +
        ((LA and LB) xor (LA and LC) xor (LB and LC));
      LH := LG; LG := LF; LF := LE; LE := LD + LT1;
      LD := LC; LC := LB; LB := LA; LA := LT1 + LT2;
    end;

    LPState[0] := LPState[0] + LA; LPState[1] := LPState[1] + LB;
    LPState[2] := LPState[2] + LC; LPState[3] := LPState[3] + LD;
    LPState[4] := LPState[4] + LE; LPState[5] := LPState[5] + LF;
    LPState[6] := LPState[6] + LG; LPState[7] := LPState[7] + LH;

    FillChar(LW, SizeOf(LW), 0);
    Inc(LPData, 64);
    Dec(ANumBlocks);
  end;
end;

{$IFDEF CPUX86_64}

{ ------------------------------------------------------------- x86-64 }

const
  // From HashLib4Pascal's HlpSHA2_256X86Backend: the byte-swap mask of the
  // SHA-NI kernel, and the table of the AVX2 kernel.
  BSWAP32_MASK: array [0 .. 3] of UInt32 = (
    $00010203, $04050607, $08090A0B, $0C0D0E0F
  );

  K256_Doubled: array [0 .. 151] of UInt32 = (
    $428A2F98, $71374491, $B5C0FBCF, $E9B5DBA5,
    $428A2F98, $71374491, $B5C0FBCF, $E9B5DBA5,
    $3956C25B, $59F111F1, $923F82A4, $AB1C5ED5,
    $3956C25B, $59F111F1, $923F82A4, $AB1C5ED5,
    $D807AA98, $12835B01, $243185BE, $550C7DC3,
    $D807AA98, $12835B01, $243185BE, $550C7DC3,
    $72BE5D74, $80DEB1FE, $9BDC06A7, $C19BF174,
    $72BE5D74, $80DEB1FE, $9BDC06A7, $C19BF174,
    $E49B69C1, $EFBE4786, $0FC19DC6, $240CA1CC,
    $E49B69C1, $EFBE4786, $0FC19DC6, $240CA1CC,
    $2DE92C6F, $4A7484AA, $5CB0A9DC, $76F988DA,
    $2DE92C6F, $4A7484AA, $5CB0A9DC, $76F988DA,
    $983E5152, $A831C66D, $B00327C8, $BF597FC7,
    $983E5152, $A831C66D, $B00327C8, $BF597FC7,
    $C6E00BF3, $D5A79147, $06CA6351, $14292967,
    $C6E00BF3, $D5A79147, $06CA6351, $14292967,
    $27B70A85, $2E1B2138, $4D2C6DFC, $53380D13,
    $27B70A85, $2E1B2138, $4D2C6DFC, $53380D13,
    $650A7354, $766A0ABB, $81C2C92E, $92722C85,
    $650A7354, $766A0ABB, $81C2C92E, $92722C85,
    $A2BFE8A1, $A81A664B, $C24B8B70, $C76C51A3,
    $A2BFE8A1, $A81A664B, $C24B8B70, $C76C51A3,
    $D192E819, $D6990624, $F40E3585, $106AA070,
    $D192E819, $D6990624, $F40E3585, $106AA070,
    $19A4C116, $1E376C08, $2748774C, $34B0BCB5,
    $19A4C116, $1E376C08, $2748774C, $34B0BCB5,
    $391C0CB3, $4ED8AA4A, $5B9CCA4F, $682E6FF3,
    $391C0CB3, $4ED8AA4A, $5B9CCA4F, $682E6FF3,
    $748F82EE, $78A5636F, $84C87814, $8CC70208,
    $748F82EE, $78A5636F, $84C87814, $8CC70208,
    $90BEFFFA, $A4506CEB, $BEF9A3F7, $C67178F2,
    $90BEFFFA, $A4506CEB, $BEF9A3F7, $C67178F2,
    $00010203, $04050607, $08090A0B, $0C0D0E0F,
    $00010203, $04050607, $08090A0B, $0C0D0E0F,
    $03020100, $0B0A0908, $FFFFFFFF, $FFFFFFFF,
    $03020100, $0B0A0908, $FFFFFFFF, $FFFFFFFF,
    $FFFFFFFF, $FFFFFFFF, $03020100, $0B0A0908,
    $FFFFFFFF, $FFFFFFFF, $03020100, $0B0A0908
  );

type
  TCpuIdResult = record
    RegEAX, RegEBX, RegECX, RegEDX: UInt32;
  end;

procedure CpuIdQuery(ALeaf, ASubLeaf: UInt32; out AResult: TCpuIdResult);
  {$I HlpCpuIdQuery.inc}
end;

procedure XGetBvQuery(out AResult: UInt64);
  {$I HlpXGetBvQuery.inc}
end;

// The kernels keep their own frame on rbp/rsp in nostackframe procedures,
// which the assembler warns about; HashLib4Pascal builds them with the
// warnings off too.
{$WARNINGS OFF}
procedure SHA256_Compress_ShaNi(AState, AData: Pointer; ANumBlocks: UInt32;
  AConstants, AMask: Pointer);
  {$I HlpSimdProc5Begin_x86_64.inc}
  {$I SHA256CompressShaNi_x86_64.inc}
end;

procedure SHA256_Compress_ShaNi_Wrap(AState, AData: Pointer; ANumBlocks: UInt32);
begin
  SHA256_Compress_ShaNi(AState, AData, ANumBlocks, @K256, @BSWAP32_MASK);
end;

procedure SHA256_Compress_Avx2(AState, AData: Pointer; ANumBlocks: UInt32;
  AConstants: Pointer);
  {$I HlpSimdProc4Begin_x86_64.inc}
  {$I SHA256CompressAvx2_x86_64.inc}
end;

{$WARNINGS ON}

procedure SHA256_Compress_Avx2_Wrap(AState, AData: Pointer; ANumBlocks: UInt32);
begin
  SHA256_Compress_Avx2(AState, AData, ANumBlocks, @K256_Doubled);
end;

function MaxLeaf: UInt32;
var R: TCpuIdResult;
begin
  CpuIdQuery(0, 0, R);
  Result := R.RegEAX;
end;

{ SHA-NI (leaf 7 EBX bit 29); the kernel also uses SSSE3 and SSE4.1 (leaf 1
  ECX bits 9 and 19). }
function HasShaNi: Boolean;
var R: TCpuIdResult;
begin
  if MaxLeaf < 7 then Exit(False);
  CpuIdQuery(1, 0, R);
  if (R.RegECX and ((1 shl 9) or (1 shl 19))) <> ((1 shl 9) or (1 shl 19)) then Exit(False);
  CpuIdQuery(7, 0, R);
  Result := (R.RegEBX and (1 shl 29)) <> 0;
end;

{ AVX2 (leaf 7 EBX bit 5) with the OS saving the AVX state (OSXSAVE, leaf 1
  ECX bit 27, and XCR0 bits 1 and 2), as HashLib4Pascal checks, and BMI2
  (leaf 7 EBX bit 8), which the kernel's rorx and andn need. }
function HasAvx2: Boolean;
var R: TCpuIdResult; Xcr0: UInt64;
begin
  if MaxLeaf < 7 then Exit(False);
  CpuIdQuery(1, 0, R);
  if (R.RegECX and (1 shl 27)) = 0 then Exit(False);
  Xcr0 := 0;
  XGetBvQuery(Xcr0);
  if (UInt32(Xcr0) and $06) <> $06 then Exit(False);
  CpuIdQuery(7, 0, R);
  Result := (R.RegEBX and ((1 shl 5) or (1 shl 8))) = ((1 shl 5) or (1 shl 8));
end;

{$ENDIF CPUX86_64}

{$IFDEF CPUAARCH64}

{ ------------------------------------------------------------- AArch64 }

procedure SHA256_Compress_CryptoExt(AState, AData: Pointer; ANumBlocks: UInt32;
  AConstants: Pointer);
  {$I HlpSimdProc4Begin_aarch64.inc}
  {$I SHA256CompressCryptoExt_aarch64.inc}
end;

procedure SHA256_Compress_CryptoExt_Wrap(AState, AData: Pointer; ANumBlocks: UInt32);
begin
  SHA256_Compress_CryptoExt(AState, AData, ANumBlocks, @K256);
end;

type
  TGetAuxVal = function(AType: PtrUInt): PtrUInt; cdecl;

const
  AT_HWCAP = 16;
  HWCAP_ASIMD = PtrUInt(1) shl 1;
  HWCAP_SHA2 = PtrUInt(1) shl 6;

{ The SHA-256 instructions (HWCAP_SHA2) and NEON (HWCAP_ASIMD), from glibc's
  getauxval, as HashLib4Pascal reads them on Linux. }
function HasCryptoExt: Boolean;
var Lib: TLibHandle; GetAuxVal: TGetAuxVal; Caps: PtrUInt;
begin
  Result := False;
  Lib := LoadLibrary('libc.so.6');
  if Lib = NilHandle then Exit;
  GetAuxVal := TGetAuxVal(GetProcedureAddress(Lib, 'getauxval'));
  if Assigned(GetAuxVal) then
  begin
    Caps := GetAuxVal(AT_HWCAP);
    Result := (Caps and (HWCAP_ASIMD or HWCAP_SHA2)) = (HWCAP_ASIMD or HWCAP_SHA2);
  end;
  UnloadLibrary(Lib);
end;

{$ENDIF CPUAARCH64}

{ ------------------------------------------------------------ selection }

var
  Available: array[TSha256Kernel] of Boolean;

function Sha256Kernel: TSha256Kernel;
begin
  Result := Active;
end;

function Sha256HasKernel(K: TSha256Kernel): Boolean;
begin
  Result := Available[K];
end;

function Sha256UseKernel(K: TSha256Kernel): Boolean;
begin
  Result := Available[K];
  if not Result then Exit;
  case K of
    skScalar: SHA256_Compress := @SHA256_Compress_Scalar;
{$IFDEF CPUX86_64}
    skAvx2: SHA256_Compress := @SHA256_Compress_Avx2_Wrap;
    skShaNi: SHA256_Compress := @SHA256_Compress_ShaNi_Wrap;
{$ENDIF}
{$IFDEF CPUAARCH64}
    skCryptoExt: SHA256_Compress := @SHA256_Compress_CryptoExt_Wrap;
{$ENDIF}
  end;
  Active := K;
end;

initialization
  Available[skScalar] := True;
{$IFDEF CPUX86_64}
  Available[skAvx2] := HasAvx2;
  Available[skShaNi] := HasShaNi;
{$ENDIF}
{$IFDEF CPUAARCH64}
  Available[skCryptoExt] := HasCryptoExt;
{$ENDIF}
  if not (Sha256UseKernel(skShaNi) or Sha256UseKernel(skCryptoExt) or Sha256UseKernel(skAvx2)) then
    Sha256UseKernel(skScalar);

end.
