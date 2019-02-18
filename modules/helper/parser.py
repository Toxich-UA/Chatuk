import collections



# def update(dst, src, overwrite=True):
#     for k, v in src.items():
#         has_key = k in dst
#         dst_type = type(dst.get(k, v))
#
#         # print("Key: {0} | Value: {1}".format(k, v))
#         if has_key:
#             dst[k] = v
#         else:
#             dst[k] = dst_type(v)
#     return dst

def update(dst, src, overwrite=True):
    for k, v in src.items():
        has_key = k in dst
        dst_type = type(dst.get(k, v))

        if isinstance(v, collections.Mapping):
            r = update(dst.get(k, {}), v, overwrite=overwrite)
            dst[k] = r
        else:
            if has_key:
                    if hasattr(dst[k], '_value'):
                        dst[k].value = v.value
                    else:
                        dst[k] = dst_type(v)
            else:
                dst[k] = dst_type(v)
    return dst
