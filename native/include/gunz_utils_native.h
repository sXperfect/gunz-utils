#ifndef GUNZ_UTILS_NATIVE_H
#define GUNZ_UTILS_NATIVE_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GUNZ_UTILS_NATIVE_VERSION "0.1.0"

/*
 * Encode an unsigned 64-bit integer into a canonical varint.
 * Out buffer must have at least 10 bytes capacity.
 * Returns the number of bytes written (1 to 10).
 */
size_t gunz_native_encode_uvarint(uint64_t value, uint8_t *out);

/*
 * Decode an unsigned 64-bit integer from a canonical varint buffer.
 * Parameters:
 *   buf: pointer to buffer start
 *   len: available bytes in buffer
 *   out_val: pointer to receive the decoded uint64_t
 *   out_bytes_read: pointer to receive the number of bytes read
 *
 * Returns status code:
 *    0: success
 *   -1: EOF / buffer too short before termination
 *   -2: varint exceeds 64 bits (10th byte > 1)
 *   -3: varint is too long (> 10 bytes without terminal byte)
 *   -4: non-canonical varint (redundant zero byte)
 */
int gunz_native_decode_uvarint(
    const uint8_t *buf,
    size_t len,
    uint64_t *out_val,
    size_t *out_bytes_read
);

#ifdef __cplusplus
}
#endif

#endif /* GUNZ_UTILS_NATIVE_H */
