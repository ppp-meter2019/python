"""
    bencode library
    # bencoding
    # http://www.bittorrent.org/beps/bep_0003.html
"""


from functools import singledispatch
from collections import OrderedDict
from collections.abc import Sequence, Mapping

I, L, D, E, C = b'ilde:'


def dict_to_list(val):
    for k,v in val:
        yield k
        yield v


@singledispatch
def encode_any(val, interim_s):
    raise NotImplemented


@encode_any.register(int)
def encode_int(val, interim_s):
    interim_s.append(I)
    interim_s.extend(str(val).encode())
    interim_s.append(E)


@encode_any.register(bytes)
def encode_bytes(val, interim_s):
    interim_s.extend(str(len(val)).encode())
    interim_s.append(C)
    interim_s.extend(val)


@encode_any.register(str)
def encode_str(val, interim_s):
    encode_any(val.encode('utf-8'), interim_s)


def encode_seq(val, interim_s, type_):
    interim_s.append(type_)
    for item in val:
        encode_any(item, interim_s)
    interim_s.append(E)


@encode_any.register(Sequence)
def encode_list(val, interim_s):
    encode_seq(val,interim_s, L)


@encode_any.register(OrderedDict)
def encode_dict(val, interim_s):
    encode_seq(dict_to_list(val.items()), interim_s, D)


@encode_any.register(Mapping)
def encode_dict(val, interim_s):
    encode_seq(dict_to_list(sorted(val.items())), interim_s, D)


def encode(val):
    interim_s = bytearray()
    encode_any(val, interim_s)
    return bytes(interim_s)


# =========================================
#       Decode
# =========================================


def decode_int(b_val, index_, separator_=E):
    if separator_ == E:
        index_ += 1
    val_end_index = b_val.index(separator_, index_)
    res = b_val[index_: val_end_index]

    if len(res) > 1 and chr(res[0]) == '0':
        raise ValueError(f"invalid literal for int() with base 0: '{res.decode()}'")
    else:
        return int(res), val_end_index + 1


def decode_bytes(b_val, index_):
    b_str_len, int_end_index = decode_int(b_val, index_, separator_=C)
    res = b_val[int_end_index: int_end_index + b_str_len]
    return res, int_end_index + b_str_len


def push_seq(b_val, index_):
    return LIST_MARK, index_ + 1


def push_dict(b_val, index_):
    return DICT_MARK, index_ + 1


def build_dict(seq):
    return OrderedDict(zip(*[iter(seq)] * 2))


LIST_MARK = object()
DICT_MARK = object()

TYPES_DICT = {
    I: decode_int,
    L: push_seq,
    D: push_dict,
    E: lambda _, i: (None, i)
}


def decode(b_val):
    index_ = 0
    decode_stack = []
    b_val_lenght = len(b_val)
    curr_char = ''

    while True:
        try:
            curr_char = b_val[index_]
        except Exception as e:
            raise ValueError(f"Wrong input value {b_val}")

        part_, index_ = TYPES_DICT.get(curr_char, decode_bytes)(b_val, index_)

        if part_ is None:
            # NONE is an  e - mark,  - is the mark of the end of list or dict
            accum = []
            while True:
                # if stack is empty, then we have data inconsistency: 'e' without 'l' or 'd' earlier
                if not decode_stack:
                    raise ValueError(f"Wrong input value. "
                                     f"Data integrity is compromised: 'e' without 'l' or 'd' earlier")
                temp_ = decode_stack.pop()
                if temp_ == LIST_MARK:
                    part_ = list(reversed(accum))
                    index_ += 1
                    break
                elif temp_ == DICT_MARK:
                    part_ = build_dict(reversed(accum))
                    index_ += 1
                    break
                else:
                    accum.append(temp_)
        elif part_ in (LIST_MARK, DICT_MARK):
            decode_stack.append(part_)
            continue

        # if stack is empty it shows that we have the result, or the error if last char index != index_
        if not decode_stack:
            if index_ < b_val_lenght:
                raise ValueError(f"Wrong input value. "
                                 f"Data integrity is compromised: additional data after "
                                 f"the end of sequence - '{b_val[index_:]}'")
            return part_

        else:
            decode_stack.append(part_)