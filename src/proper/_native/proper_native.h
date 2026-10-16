/* proper_native.h - the C interface of libproper_native.so
   (proper_native.pas, whose header comment describes it).

   proper/_native hands this file to cffi, which accepts no preprocessor
   directive: keep the declarations plain C. */

const char *proper_native_version(void);

/* The size of a prepared HMAC-SHA256 key. */
size_t proper_hmac_key_size(void);
/* Prepares an HMAC-SHA256 key of any length into out. */
void proper_hmac_key(const unsigned char *key, size_t len, void *out);
/* Prepares into out the signing key of a secret key and a salt: the
   HMAC-SHA256 of the salt keyed with the secret. */
void proper_derive_key(const char *secret, size_t secret_len, const char *salt,
                       size_t salt_len, void *out);
void proper_hmac_sha256(const void *key, const char *msg, size_t len, unsigned char *digest);

/* For the tests: SHA-256 of a message; the kernel (0 scalar, 1 AVX2,
   2 SHA-NI, 3 ARM crypto extensions); switch to one (1 done, 0 not here). */
void proper_sha256(const char *msg, size_t len, unsigned char *digest);
int proper_sha256_kernel(void);
int proper_sha256_use(int kernel);

/* Signed tokens: a length, or -1 bad signature, -2 expired, -3 malformed,
   -4 a buffer too small. */
size_t proper_deflate_size(void);
int proper_deflate_init(void *stream);
void proper_deflate_end(void *stream);
long long proper_sign_json(const void *key, void *stream, const char *json, size_t len,
                           long long timestamp, char *out, size_t cap,
                           char *scratch, size_t scratch_cap);
long long proper_unsign(const void *keys, int count, int timed, const char *token, size_t len,
                        long long now, long long max_age, char *out, size_t cap,
                        char *scratch, size_t scratch_cap, long long *timestamp);

/* Request bodies (proper_forms.pas). Records are 64-bit offsets and
   lengths: a field is name, value (4); a parameter is key, value (4), the
   type first; a part is name, filename (-1 none), content-type (-1 none),
   data, headers (10). -4: a buffer too small; the multipart errors are
   -10 malformed, -11 unfinished, -12 no Content-Disposition, -13 no name,
   -14 too many fields, -15 too many files, -16 a field too big,
   -17 headers too many or too big. */
long long proper_parse_form(const char *body, size_t len, char *out, size_t cap,
                            long long *fields, ptrdiff_t max_fields);
long long proper_parse_params(const char *value, size_t len, char *out, size_t cap,
                              long long *recs, ptrdiff_t max_recs);
long long proper_parse_multipart(const char *body, size_t len, const char *boundary,
                                 size_t boundary_len, char *out, size_t cap,
                                 long long *parts, ptrdiff_t max_parts, long long max_fields,
                                 long long max_files, long long max_field_size,
                                 long long *recs, ptrdiff_t max_recs);

/* HTML to plain text (proper_text.pas): the length of the text, or -4 when
   out, scratch or links is too small. names: the filename of each
   attachment by its sgid, as records of offsets and lengths into the names
   bytes (4); links: room for links_cap open links (3 words each). */
long long proper_html2text(const char *html, size_t len, const char *names,
                           const long long *name_recs, ptrdiff_t name_count, char *out,
                           size_t cap, char *scratch, size_t scratch_cap, long long *links,
                           ptrdiff_t links_cap);
