#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <stddef.h>
#include <math.h>
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
 * Recursive validation of pure JSON objects (no custom classes or byte objects).
 */
static int check_json_clean(PyObject *obj, int depth, int max_depth);

static int check_json_clean_inner(PyObject *obj, int depth, int max_depth) {
    if (depth > max_depth) {
        PyErr_Format(
            PyExc_ValueError,
            "object hierarchy exceeds maximum nesting depth (%d)",
            max_depth
        );
        return -1;
    }
    /* CPython 3.12+ separates some C/Python recursion accounting. A hard
     * fast-path budget bounds our C stack independently of those internals.
     * Returning false delegates deeper input to the Python reference, which
     * applies its own recursion/depth semantics rather than changing the API. */
    if (depth > 128) {
        return 0;
    }
    if (PyBytes_Check(obj)) {
        PyErr_SetString(
            PyExc_TypeError,
            "bytes are not implicitly JSON serializable"
        );
        return -1;
    }
    if (obj == Py_None || PyBool_Check(obj) || PyUnicode_CheckExact(obj) || PyLong_CheckExact(obj)) {
        return 1;
    }
    if (PyFloat_CheckExact(obj)) {
        double d = PyFloat_AS_DOUBLE(obj);
        if (isnan(d) || isinf(d)) {
            PyErr_SetString(
                PyExc_ValueError,
                "Out of range float values are not JSON compliant"
            );
            return -1;
        }
        return 1;
    }
    if (PyList_CheckExact(obj)) {
        Py_ssize_t len = PyList_GET_SIZE(obj);
        for (Py_ssize_t i = 0; i < len; i++) {
            PyObject *item = PyList_GET_ITEM(obj, i);
            int rc = check_json_clean(item, depth + 1, max_depth);
            if (rc <= 0) return rc;
        }
        return 1;
    }
    if (PyDict_CheckExact(obj)) {
        PyObject *key, *val;
        Py_ssize_t pos = 0;
        while (PyDict_Next(obj, &pos, &key, &val)) {
            if (!PyUnicode_CheckExact(key)) {
                return 0; /* non-string key requires normalization */
            }
            int rc = check_json_clean(val, depth + 1, max_depth);
            if (rc <= 0) return rc;
        }
        return 1;
    }
    return 0; /* custom type or non-exact container */
}

/* Balance CPython recursion accounting on every success/failure path. */
static int check_json_clean(PyObject *obj, int depth, int max_depth) {
    if (Py_EnterRecursiveCall(" while validating JSON objects")) {
        return -1;
    }
    int result = check_json_clean_inner(obj, depth, max_depth);
    Py_LeaveRecursiveCall();
    return result;
}

/*
 * Python C API wrapper for is_json_clean.
 */
static PyObject *py_is_json_clean(PyObject *self, PyObject *args) {
    PyObject *obj;
    int max_depth = 100;
    if (!PyArg_ParseTuple(args, "O|i", &obj, &max_depth)) {
        return NULL;
    }
    int rc = check_json_clean(obj, 0, max_depth);
    if (rc < 0) {
        return NULL;
    }
    if (rc == 1) {
        Py_RETURN_TRUE;
    }
    Py_RETURN_FALSE;
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

    /* Python integer subclasses may override arithmetic/comparison. Delegate
     * them to the reference instead of silently bypassing those semantics. */
    if (!PyLong_CheckExact(py_val) && !PyBool_Check(py_val)) {
        PyObject *module = PyImport_ImportModule("gunz_utils.binary");
        if (!module) return NULL;
        PyObject *encoder = PyObject_GetAttrString(module, "_py_encode_uvarint");
        Py_DECREF(module);
        if (!encoder) return NULL;
        PyObject *result = PyObject_CallOneArg(encoder, py_val);
        Py_DECREF(encoder);
        return result;
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

static inline void swap_double(double *a, double *b) {
    double t = *a;
    *a = *b;
    *b = t;
}

static int compare_doubles_c(const void *a, const void *b) {
    double da = *(const double *)a;
    double db = *(const double *)b;
    if (da < db) return -1;
    if (da > db) return 1;
    return 0;
}

void gunz_native_introselect(double *arr, size_t left, size_t right, size_t k, int depth_limit) {
    while (left < right) {
        if (right - left < 16) {
            for (size_t i = left + 1; i <= right; ++i) {
                double key = arr[i];
                size_t j = i;
                while (j > left && arr[j - 1] > key) {
                    arr[j] = arr[j - 1];
                    j--;
                }
                arr[j] = key;
            }
            return;
        }

        if (depth_limit <= 0) {
            qsort(arr + left, right - left + 1, sizeof(double), compare_doubles_c);
            return;
        }
        depth_limit--;

        size_t mid = left + (right - left) / 2;
        if (arr[mid] < arr[left]) swap_double(&arr[left], &arr[mid]);
        if (arr[right] < arr[left]) swap_double(&arr[left], &arr[right]);
        if (arr[right] < arr[mid]) swap_double(&arr[mid], &arr[right]);

        double pivot = arr[mid];
        size_t lt = left;
        size_t gt = right;
        size_t i = left;
        while (i <= gt) {
            if (arr[i] < pivot) {
                swap_double(&arr[lt], &arr[i]);
                lt++;
                i++;
            } else if (arr[i] > pivot) {
                swap_double(&arr[i], &arr[gt]);
                if (gt == 0) break;
                gt--;
            } else {
                i++;
            }
        }

        if (k >= lt && k <= gt) {
            return;
        } else if (k < lt) {
            if (lt == 0) return;
            right = lt - 1;
        } else {
            left = gt + 1;
        }
    }
}

static PyObject *py_update_running_stats(PyObject *self, PyObject *args) {
    long long count;
    double mean, m2, min_val, max_val, total;
    PyObject *iterable;
    if (!PyArg_ParseTuple(args, "LdddddO", &count, &mean, &m2, &min_val, &max_val, &total, &iterable)) {
        return NULL;
    }
    PyObject *fast = PySequence_Fast(iterable, "values must be an iterable sequence");
    if (!fast) return NULL;
    Py_ssize_t n = PySequence_Fast_GET_SIZE(fast);
    PyObject **items = PySequence_Fast_ITEMS(fast);
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *item = items[i];
        if (PyBool_Check(item)) {
            Py_DECREF(fast);
            PyErr_SetString(PyExc_TypeError, "value must be real numeric");
            return NULL;
        }
        if (!PyFloat_CheckExact(item) && !PyLong_CheckExact(item)) {
            Py_DECREF(fast);
            Py_RETURN_NONE;
        }
        double val = PyFloat_AsDouble(item);
        if (PyErr_Occurred()) {
            Py_DECREF(fast);
            return NULL;
        }
        if (isnan(val) || isinf(val)) {
            Py_DECREF(fast);
            PyErr_SetString(PyExc_ValueError, "value must be finite");
            return NULL;
        }
        count++;
        double delta = val - mean;
        mean += delta / (double)count;
        double delta2 = val - mean;
        m2 += delta * delta2;
        total += val;
        if (val < min_val) min_val = val;
        if (val > max_val) max_val = val;
        if (!isfinite(mean) || !isfinite(m2)) {
            Py_DECREF(fast);
            PyErr_SetString(PyExc_OverflowError, "running statistics overflowed finite float range");
            return NULL;
        }
    }
    Py_DECREF(fast);
    return Py_BuildValue("Lddddd", count, mean, m2, min_val, max_val, total);
}

static PyObject *py_fast_summary(PyObject *self, PyObject *args) {
    PyObject *iterable;
    PyObject *percentiles_obj;
    double threshold = 3.5;
    if (!PyArg_ParseTuple(args, "OO|d", &iterable, &percentiles_obj, &threshold)) {
        return NULL;
    }
    if (threshold <= 0 || isnan(threshold) || isinf(threshold)) {
        PyErr_SetString(PyExc_ValueError, "outlier_threshold must be finite and > 0");
        return NULL;
    }

    PyObject *fast = PySequence_Fast(iterable, "values must be an iterable");
    if (!fast) return NULL;
    Py_ssize_t n = PySequence_Fast_GET_SIZE(fast);
    if (n == 0) {
        Py_DECREF(fast);
        PyErr_SetString(PyExc_ValueError, "samples must not be empty");
        return NULL;
    }
    if ((size_t)n > SIZE_MAX / sizeof(double)) {
        Py_DECREF(fast);
        return PyErr_NoMemory();
    }

    double *data = (double *)malloc((size_t)n * sizeof(double));
    if (!data) {
        Py_DECREF(fast);
        return PyErr_NoMemory();
    }

    PyObject **items = PySequence_Fast_ITEMS(fast);
    double min_val = INFINITY;
    double max_val = -INFINITY;
    double mean = 0.0;
    double m2 = 0.0;

    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *item = items[i];
        if (PyBool_Check(item)) {
            free(data);
            Py_DECREF(fast);
            PyErr_SetString(PyExc_ValueError, "samples must contain only real numeric values");
            return NULL;
        }
        if (!PyFloat_CheckExact(item) && !PyLong_CheckExact(item)) {
            free(data);
            Py_DECREF(fast);
            Py_RETURN_NONE;
        }
        double val = PyFloat_AsDouble(item);
        if (PyErr_Occurred()) {
            free(data);
            Py_DECREF(fast);
            return NULL;
        }
        if (isnan(val) || isinf(val)) {
            free(data);
            Py_DECREF(fast);
            PyErr_SetString(PyExc_ValueError, "samples must contain only finite values");
            return NULL;
        }
        data[i] = val;
        double delta = val - mean;
        mean += delta / (double)(i + 1);
        double delta2 = val - mean;
        m2 += delta * delta2;
        if (val < min_val) min_val = val;
        if (val > max_val) max_val = val;
    }
    Py_DECREF(fast);

    if (!isfinite(mean) || !isfinite(m2)) {
        free(data);
        Py_RETURN_NONE;
    }

    double variance = (n >= 1) ? (m2 / (double)n) : 0.0;
    double stdev = sqrt(variance);
    double cv = (fabs(mean) > 1e-15 && n >= 1) ? (stdev / fabs(mean)) : NAN;

    /* Sorted copy for median and percentiles */
    double *sorted_data = (double *)malloc((size_t)n * sizeof(double));
    if (!sorted_data) {
        free(data);
        return PyErr_NoMemory();
    }
    memcpy(sorted_data, data, (size_t)n * sizeof(double));
    qsort(sorted_data, (size_t)n, sizeof(double), compare_doubles_c);

    /* Median using presorted linear interpolation */
    double median_val;
    if (n % 2 == 1) {
        median_val = sorted_data[n / 2];
    } else {
        median_val = sorted_data[n / 2 - 1] + (sorted_data[n / 2] - sorted_data[n / 2 - 1]) * 0.5;
    }
    if (!isfinite(median_val)) {
        free(sorted_data);
        free(data);
        Py_RETURN_NONE;
    }

    /* Absolute deviations from median */
    double *devs = (double *)malloc((size_t)n * sizeof(double));
    if (!devs) {
        free(sorted_data);
        free(data);
        return PyErr_NoMemory();
    }
    for (Py_ssize_t i = 0; i < n; i++) {
        devs[i] = fabs(data[i] - median_val);
        if (!isfinite(devs[i])) {
            free(devs);
            free(sorted_data);
            free(data);
            Py_RETURN_NONE;
        }
    }
    qsort(devs, (size_t)n, sizeof(double), compare_doubles_c);
    double mad_val;
    if (n % 2 == 1) {
        mad_val = devs[n / 2];
    } else {
        mad_val = devs[n / 2 - 1] + (devs[n / 2] - devs[n / 2 - 1]) * 0.5;
    }
    free(devs);

    /* Percentiles dictionary */
    PyObject *pct_fast = PySequence_Fast(percentiles_obj, "percentiles must be an iterable");
    if (!pct_fast) {
        free(sorted_data);
        free(data);
        return NULL;
    }
    Py_ssize_t num_pct = PySequence_Fast_GET_SIZE(pct_fast);
    PyObject *pct_dict = PyDict_New();
    if (!pct_dict) {
        Py_DECREF(pct_fast);
        free(sorted_data);
        free(data);
        return NULL;
    }
    PyObject **pct_items = PySequence_Fast_ITEMS(pct_fast);
    for (Py_ssize_t i = 0; i < num_pct; i++) {
        double q = PyFloat_AsDouble(pct_items[i]);
        if (PyErr_Occurred() || q < 0.0 || q > 1.0 || isnan(q)) {
            Py_DECREF(pct_dict);
            Py_DECREF(pct_fast);
            free(sorted_data);
            free(data);
            if (!PyErr_Occurred()) {
                PyErr_SetString(PyExc_ValueError, "percentile q must be finite and between 0 and 1");
            }
            return NULL;
        }
        double pos = (double)(n - 1) * q;
        Py_ssize_t lower = (Py_ssize_t)floor(pos);
        Py_ssize_t upper = (Py_ssize_t)ceil(pos);
        double pct_val;
        if (lower == upper) {
            pct_val = sorted_data[lower];
        } else {
            double frac = pos - (double)lower;
            pct_val = sorted_data[lower] + (sorted_data[upper] - sorted_data[lower]) * frac;
        }
        PyObject *py_q = PyFloat_FromDouble(q);
        PyObject *py_val = PyFloat_FromDouble(pct_val);
        if (!py_q || !py_val || PyDict_SetItem(pct_dict, py_q, py_val) < 0) {
            Py_XDECREF(py_q);
            Py_XDECREF(py_val);
            Py_DECREF(pct_dict);
            Py_DECREF(pct_fast);
            free(sorted_data);
            free(data);
            return NULL;
        }
        Py_DECREF(py_q);
        Py_DECREF(py_val);
    }
    Py_DECREF(pct_fast);
    free(sorted_data);

    /* Outliers */
    PyObject *outliers_list = PyList_New(0);
    if (!outliers_list) {
        Py_DECREF(pct_dict);
        free(data);
        return NULL;
    }
    if (mad_val > 1e-15) {
        double scale = 0.6744897501960817;
        double inv_denom = scale / mad_val;
        for (Py_ssize_t i = 0; i < n; i++) {
            if (fabs(data[i] - median_val) * inv_denom > threshold) {
                PyObject *idx = PyLong_FromSsize_t(i);
                if (!idx || PyList_Append(outliers_list, idx) < 0) {
                    Py_XDECREF(idx);
                    Py_DECREF(outliers_list);
                    Py_DECREF(pct_dict);
                    free(data);
                    return NULL;
                }
                Py_DECREF(idx);
            }
        }
    }
    free(data);
    PyObject *outliers_tuple = PyList_AsTuple(outliers_list);
    Py_DECREF(outliers_list);
    if (!outliers_tuple) {
        Py_DECREF(pct_dict);
        return NULL;
    }

    PyObject *cv_obj = isnan(cv) ? Py_NewRef(Py_None) : PyFloat_FromDouble(cv);
    if (!cv_obj) {
        Py_DECREF(pct_dict);
        Py_DECREF(outliers_tuple);
        return NULL;
    }

    return Py_BuildValue(
        "{s:n,s:d,s:d,s:d,s:d,s:d,s:d,s:N,s:d,s:N,s:N}",
        "count", n,
        "minimum", min_val,
        "maximum", max_val,
        "mean", mean,
        "median", median_val,
        "variance", variance,
        "stdev", stdev,
        "coefficient_of_variation", cv_obj,
        "mad", mad_val,
        "percentiles", pct_dict,
        "outlier_indices", outliers_tuple
    );
}

static PyObject *py_merge_running_stats(PyObject *self, PyObject *args) {
    long long count_a, count_b;
    double mean_a, m2_a, min_a, max_a, total_a;
    double mean_b, m2_b, min_b, max_b, total_b;
    if (!PyArg_ParseTuple(
        args,
        "LdddddLddddd",
        &count_a, &mean_a, &m2_a, &min_a, &max_a, &total_a,
        &count_b, &mean_b, &m2_b, &min_b, &max_b, &total_b
    )) {
        return NULL;
    }
    if (count_a == 0) {
        return Py_BuildValue("Lddddd", count_b, mean_b, m2_b, min_b, max_b, total_b);
    }
    if (count_b == 0) {
        return Py_BuildValue("Lddddd", count_a, mean_a, m2_a, min_a, max_a, total_a);
    }
    long long combined_count = count_a + count_b;
    double delta = mean_b - mean_a;
    double combined_mean = mean_a + delta * ((double)count_b / (double)combined_count);
    double combined_m2 = m2_a + m2_b + (delta * delta) * ((double)count_a * (double)count_b / (double)combined_count);
    if (!isfinite(combined_mean) || !isfinite(combined_m2)) {
        PyErr_SetString(PyExc_OverflowError, "running statistics overflowed finite float range");
        return NULL;
    }
    double combined_total = total_a + total_b;
    double combined_min = (min_a < min_b) ? min_a : min_b;
    double combined_max = (max_a > max_b) ? max_a : max_b;
    return Py_BuildValue("Lddddd", combined_count, combined_mean, combined_m2, combined_min, combined_max, combined_total);
}

typedef struct {
    double x;
    double y;
    Py_ssize_t original_index;
} Point2D;

static int compare_points_2d(const void *a, const void *b) {
    const Point2D *p1 = (const Point2D *)a;
    const Point2D *p2 = (const Point2D *)b;
    if (p1->x < p2->x) return -1;
    if (p1->x > p2->x) return 1;
    if (p1->y < p2->y) return -1;
    if (p1->y > p2->y) return 1;
    return 0;
}

static PyObject *py_fast_pareto_2d(PyObject *self, PyObject *args) {
    PyObject *seq_obj;
    if (!PyArg_ParseTuple(args, "O", &seq_obj)) {
        return NULL;
    }
    PyObject *fast = PySequence_Fast(seq_obj, "points must be a sequence");
    if (!fast) return NULL;
    Py_ssize_t n = PySequence_Fast_GET_SIZE(fast);
    if (n == 0) {
        Py_DECREF(fast);
        return PyTuple_New(0);
    }
    if ((size_t)n > SIZE_MAX / sizeof(Point2D)) {
        Py_DECREF(fast);
        return PyErr_NoMemory();
    }
    Point2D *pts = (Point2D *)malloc((size_t)n * sizeof(Point2D));
    if (!pts) {
        Py_DECREF(fast);
        return PyErr_NoMemory();
    }
    PyObject **items = PySequence_Fast_ITEMS(fast);
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *pt = items[i];
        if (!PyTuple_Check(pt) || PyTuple_GET_SIZE(pt) != 2) {
            free(pts);
            Py_DECREF(fast);
            Py_RETURN_NONE;
        }
        PyObject *item_x = PyTuple_GET_ITEM(pt, 0);
        PyObject *item_y = PyTuple_GET_ITEM(pt, 1);
        if (PyBool_Check(item_x) || PyBool_Check(item_y)) {
            free(pts);
            Py_DECREF(fast);
            Py_RETURN_NONE;
        }
        if (!PyFloat_CheckExact(item_x) && !PyLong_CheckExact(item_x)) {
            free(pts);
            Py_DECREF(fast);
            Py_RETURN_NONE;
        }
        if (!PyFloat_CheckExact(item_y) && !PyLong_CheckExact(item_y)) {
            free(pts);
            Py_DECREF(fast);
            Py_RETURN_NONE;
        }
        double x = PyFloat_AsDouble(item_x);
        double y = PyFloat_AsDouble(item_y);
        if (PyErr_Occurred()) {
            free(pts);
            Py_DECREF(fast);
            return NULL;
        }
        if (isnan(x) || isinf(x) || isnan(y) || isinf(y)) {
            free(pts);
            Py_DECREF(fast);
            PyErr_SetString(PyExc_ValueError, "objective values must be finite");
            return NULL;
        }
        pts[i].x = x;
        pts[i].y = y;
        pts[i].original_index = i;
    }
    Py_DECREF(fast);

    qsort(pts, (size_t)n, sizeof(Point2D), compare_points_2d);

    Py_ssize_t *frontier = (Py_ssize_t *)malloc((size_t)n * sizeof(Py_ssize_t));
    if (!frontier) {
        free(pts);
        return PyErr_NoMemory();
    }
    Py_ssize_t frontier_len = 0;
    double min_y = INFINITY;
    Py_ssize_t idx = 0;

    while (idx < n) {
        double curr_x = pts[idx].x;
        Py_ssize_t group_start = idx;
        while (idx < n && pts[idx].x <= curr_x) {
            idx++;
        }
        double group_min_y = pts[group_start].y;
        if (group_min_y < min_y) {
            for (Py_ssize_t j = group_start; j < idx; j++) {
                if (pts[j].y <= group_min_y) {
                    frontier[frontier_len++] = pts[j].original_index;
                }
            }
            min_y = group_min_y;
        }
    }
    free(pts);

    PyObject *result_tuple = PyTuple_New(frontier_len);
    if (!result_tuple) {
        free(frontier);
        return NULL;
    }
    for (Py_ssize_t i = 0; i < frontier_len; i++) {
        PyObject *idx_obj = PyLong_FromSsize_t(frontier[i]);
        if (!idx_obj) {
            Py_DECREF(result_tuple);
            free(frontier);
            return NULL;
        }
        PyTuple_SET_ITEM(result_tuple, i, idx_obj);
    }
    free(frontier);
    return result_tuple;
}

static PyObject *py_has_accel(PyObject *self, PyObject *Py_UNUSED(ignored)) {
    Py_RETURN_TRUE;
}

static PyMethodDef AccelMethods[] = {
    {"encode_uvarint", py_encode_uvarint, METH_VARARGS, "Encode uint64 into canonical varint bytes in C."},
    {"decode_uvarint", py_decode_uvarint, METH_VARARGS, "Zero-copy decode uint64 varint from buffer at offset."},
    {"is_json_clean", py_is_json_clean, METH_VARARGS, "Check if object graph consists solely of pure JSON primitives."},
    {"update_running_stats", py_update_running_stats, METH_VARARGS, "Batch update RunningStats in C."},
    {"merge_running_stats", py_merge_running_stats, METH_VARARGS, "Chan parallel merge of two RunningStats in C."},
    {"fast_summary", py_fast_summary, METH_VARARGS, "Fast vector summary computation in C."},
    {"fast_pareto_2d", py_fast_pareto_2d, METH_VARARGS, "Fast O(N log N) 2D Pareto frontier sweep in C."},
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
