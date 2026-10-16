/* proper_native.h - the C interface of libproper_native.so
   (proper_native.pas, whose header comment describes it).

   proper/_native hands this file to cffi, which accepts no preprocessor
   directive: keep the declarations plain C. */

const char *proper_native_version(void);

/* The size of a prepared HMAC-SHA256 key. */
size_t proper_hmac_key_size(void);
/* Prepares a key of at most 64 bytes into out: 0 ok, -1 a longer key. */
int proper_hmac_key(const unsigned char *key, size_t len, void *out);
void proper_hmac_sha256(const void *key, const char *msg, size_t len, unsigned char *digest);

/* For the tests: SHA-256 of a message; the kernel (0 scalar, 1 AVX2,
   2 SHA-NI, 3 ARM crypto extensions); switch to one (1 done, 0 not here). */
void proper_sha256(const char *msg, size_t len, unsigned char *digest);
int proper_sha256_kernel(void);
int proper_sha256_use(int kernel);

/* Signed tokens: a length, or -1 bad signature, -2 expired, -3 malformed,
   -4 a buffer too small. */
long long proper_sign(const void *key, const char *payload, size_t len, long long timestamp,
                      char *out, size_t cap);
long long proper_unsign(const void *keys, int count, int timed, const char *token, size_t len,
                        long long now, long long max_age, char *out, size_t cap,
                        char *scratch, size_t scratch_cap, long long *timestamp);
