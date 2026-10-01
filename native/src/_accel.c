#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <stddef.h>
#include "../include/gunz_utils_native.h"

/*
 * Pure C implementation of canonical unsigned 64-bit varint encoding.
 */
size_t gunz_native_encode_uvarint(uint64_t value, uint8_t *out) {
    size_t i = 0;
    while (1) {
        uint8_t byte = (uint8_t)(value & 0x7F);
        value >>= 7;
        if (value != 0) {
            byte |= 0x80;
            out[i++] = byte;
        } else {
            out[i++] = byte;
            break;
        }
    }
    return i;
}

/*
 * Pure C implementation of canonical unsigned 64-bit varint decoding.
 */
int gunz_native_decode_uvarint(
    const uint8_t *buf,
    size_t len,
    uint64_t *out_val,
    size_t *out_bytes_read
) {
    if (len == 0) {
        return -1; /* EOF */
    }
    uint64_t val = 0;
    unsigned int shift = 0;
    for (size_t i = 0; i < 10; i++) {
        if (i >= len) {
            return -1; /* EOF / truncated buffer */
        }
        uint8_t byte = buf[i];
        if (i == 9 && byte > 1) {
            return -2; /* varint exceeds 64 bits */
        }
        val |= ((uint64_t)(byte & 0x7F)) << shift;
        if (!(byte & 0x80)) {
            if (i > 0 && byte == 0) {
                return -4; /* non-canonical varint */
            }
            *out_val = val;
            *out_bytes_read = i + 1;
            return 0; /* success */
        }
        shift += 7;
    }
    return -3; /* varint is too long */
}

/*
 * Python C API wrapper for encode_uvarint.
 */
static PyObject *py_encode_uvarint(PyObject *self, PyObject *args) {
    PyObject *py_val;
    if (!PyArg_ParseTuple(args, "O", &py_val)) {
        return NULL;
    }
    if (!PyLong_Check(py_val)) {
        PyErr_SetString(PyExc_TypeError, "an integer is required");
        return NULL;
    }

    int overflow = 0;
    long long val_signed = PyLong_AsLongLongAndOverflow(py_val, &overflow);
    if (overflow < 0 || (overflow == 0 && val_signed < 0)) {
        PyErr_SetString(PyExc_ValueError, "unsigned varint requires a 64-bit unsigned integer");
        return NULL;
    }

    unsigned long long val = PyLong_AsUnsignedLongLong(py_val);
    if (PyErr_Occurred()) {
        PyErr_Clear();
        PyErr_SetString(PyExc_ValueError, "unsigned varint requires a 64-bit unsigned integer");
        return NULL;
    }

    uint8_t out[10];
    size_t n = gunz_native_encode_uvarint((uint64_t)val, out);
    return PyBytes_FromStringAndSize((const char *)out, (Py_ssize_t)n);
}

/*
 * Python C API wrapper for decode_uvarint.
 * Signature: decode_uvarint(buffer, offset) -> (value, new_offset)
 */
static PyObject *py_decode_uvarint(PyObject *self, PyObject *args) {
    PyObject *obj;
    Py_ssize_t offset = 0;
    if (!PyArg_ParseTuple(args, "On", &obj, &offset)) {
        return NULL;
    }

    Py_buffer view;
    if (PyObject_GetBuffer(obj, &view, PyBUF_SIMPLE) != 0) {
        return NULL;
    }

    if (offset < 0 || offset > view.len) {
        PyBuffer_Release(&view);
        PyErr_SetString(PyExc_EOFError, "binary read exceeds available data");
        return NULL;
    }

    size_t remaining = (size_t)(view.len - offset);
    if (remaining == 0) {
        PyBuffer_Release(&view);
        PyErr_SetString(PyExc_EOFError, "binary read exceeds available data");
        return NULL;
    }

    uint64_t val = 0;
    size_t bytes_read = 0;
    const uint8_t *ptr = (const uint8_t *)view.buf + offset;
    int rc = gunz_native_decode_uvarint(ptr, remaining, &val, &bytes_read);
    PyBuffer_Release(&view);

    if (rc == 0) {
        PyObject *py_val = PyLong_FromUnsignedLongLong(val);
        if (!py_val) return NULL;
        PyObject *py_offset = PyLong_FromSsize_t(offset + (Py_ssize_t)bytes_read);
        if (!py_offset) {
            Py_DECREF(py_val);
            return NULL;
        }
        PyObject *tuple = PyTuple_New(2);
        if (!tuple) {
            Py_DECREF(py_val);
            Py_DECREF(py_offset);
            return NULL;
        }
        PyTuple_SET_ITEM(tuple, 0, py_val);
        PyTuple_SET_ITEM(tuple, 1, py_offset);
        return tuple;
    } else if (rc == -1) {
        PyErr_SetString(PyExc_EOFError, "binary read exceeds available data");
        return NULL;
    } else if (rc == -2) {
        PyErr_SetString(PyExc_ValueError, "varint exceeds 64 bits");
        return NULL;
    } else if (rc == -3) {
        PyErr_SetString(PyExc_ValueError, "varint is too long");
        return NULL;
    } else if (rc == -4) {
        PyErr_SetString(PyExc_ValueError, "non-canonical varint");
        return NULL;
    } else {
        PyErr_SetString(PyExc_RuntimeError, "unexpected varint decode error");
        return NULL;
    }
}

static PyObject *py_has_accel(PyObject *self, PyObject *Py_UNUSED(ignored)) {
    Py_RETURN_TRUE;
}

static PyMethodDef AccelMethods[] = {
    {"encode_uvarint", py_encode_uvarint, METH_VARARGS, "Encode uint64 into canonical varint bytes in C."},
    {"decode_uvarint", py_decode_uvarint, METH_VARARGS, "Zero-copy decode uint64 varint from buffer at offset."},
    {"has_accel", py_has_accel, METH_NOARGS, "Return True indicating native C acceleration is active."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef accelmodule = {
    PyModuleDef_HEAD_INIT,
    "_accel",
    "Compiled C acceleration primitives for gunz-utils.",
    -1,
    AccelMethods
};

PyMODINIT_FUNC PyInit__accel(void) {
    return PyModule_Create(&accelmodule);
}
