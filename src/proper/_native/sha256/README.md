# SHA-256 kernels from HashLib4Pascal

The SHA-256 block compression of `../proper_native.pas`, taken from
[HashLib4Pascal](https://github.com/Xor-el/HashLib4Pascal) at commit
`8b2cd8d` (MIT license, `LICENSE`). Only what SHA-256 needs on Linux,
x86-64 and ARM64, is here.

Copied without changes:

- `SHA256CompressShaNi_x86_64.inc`, `SHA256CompressAvx2_x86_64.inc` and
  `SHA256CompressCryptoExt_aarch64.inc`, the kernels;
- `HlpSimdProc4Begin_x86_64.inc`, `HlpSimdProc5Begin_x86_64.inc`,
  `HlpSimdProc4Begin_aarch64.inc`, `HlpSimdNonVolatileSave_x86_64.inc` and
  `HlpSimdNonVolatileRestore_x86_64.inc`, their prologues;
- `HlpCpuIdQuery.inc` and `HlpXGetBvQuery.inc`, the `cpuid` and `xgetbv`
  queries.

Changed:

- In the two x86-64 kernels, the `{$I}` of the nonvolatile save and restore
  names the file alone: upstream gives a path from the unit's directory
  (`..\..\Include\Simd\Common\...`), which Free Pascal 3.2.2 resolves from
  the `.inc` and doesn't find.
- `proper_sha256.pas` replaces the 21 units the kernels came with
  (`TSHA2_256Base`, the hash classes and interfaces, `TCpuFeatures`): the
  scalar compression of `HlpSHA2_256Base` with the big-endian load and the
  rotations written out, the constant tables, and the selection of the
  kernel. It picks SHA-NI, else AVX2, on x86-64, the crypto extensions on
  ARM64, else the scalar code. The AVX2 kernel is used only when the CPU
  also has BMI2, which its `rorx` and `andn` need (upstream checks AVX2
  alone).

Left out: the i386 kernels, the SSE2 and SSSE3 kernels and the ARM64
general-register kernel (a CPU without SHA-NI, AVX2 or the crypto
extensions gets the scalar code), and the Windows, macOS and BSD code.

The tests (`tests/native/`) check every kernel the CPU has against
Python's `hashlib`.
