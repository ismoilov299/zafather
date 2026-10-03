from __future__ import annotations

import gzip
import struct

import pytest

from zafather.mtproto.tl import (
    TLDecodeError,
    TLObject,
    TLReader,
    TLSchema,
    TLTypeError,
    TLWriter,
    default_schema,
    default_serializer,
    functions,
    schema_layer,
    types,
)
from zafather.mtproto.tl.schema import (
    constructor_id,
    iter_definitions,
    parse_definition,
    parse_type,
)

SERIALIZER = default_serializer()


def test_bundled_schema_layer_and_size() -> None:
    schema = default_schema()
    assert schema_layer() == 229
    assert len(schema.constructors) > 1600 and len(schema.functions) > 800
    assert schema.constructor("inputPeerSelf").id == 0x7DA07EC9
    assert schema.function("help.getConfig").id == 0xC4F9186B
    assert schema.function("req_pq_multi").id == 0xBE7E8EF1
    assert "TLSchema layer=229" in repr(schema)


def test_declared_ids_match_crc32() -> None:
    from importlib import resources

    text = (resources.files("zafather.mtproto.tl") / "data" / "api.tl").read_text(encoding="utf-8")
    definitions = [parse_definition(line, is_function=f) for line, f in iter_definitions(text)]
    mismatches = [d for d in definitions if constructor_id(str(d)) != d.id]
    assert not mismatches, mismatches[:3]
    assert constructor_id("ipPort ipv4:int port:int = IpPort") == 0xD433AD73


def test_parse_type_and_definition() -> None:
    vector = parse_type("Vector<long>")
    assert vector.is_vector and vector.argument is not None and vector.argument.name == "long"
    assert parse_type("vector<future_salt>").bare and parse_type("!X").generic
    assert (
        parse_type("future_salt").is_bare_constructor and not parse_type("Bool").is_bare_constructor
    )
    definition = parse_definition(
        "test#00000001 flags:# a:flags.0?true b:flags.1?int c:string = Test;", is_function=False
    )
    assert [p.name for p in definition.params] == ["flags", "a", "b", "c"]
    assert definition.param("a").is_true_flag and definition.param("c").required
    assert definition.param("missing") is None
    schema = TLSchema.parse("---types---\n" + str(definition) + "\n// LAYER 7")
    assert schema.layer == 7 and schema.by_id[1].name == "test"
    with pytest.raises(KeyError):
        schema.function("nope")


def test_codec_primitives() -> None:
    writer = TLWriter().int32(-42).uint32(0xFFFFFFFF).int64(-(1 << 40)).double(1.5)
    writer.fixed(b"\x01" * 16, 16).string("salom").bytes(b"x" * 300)
    reader = TLReader(writer.to_bytes())
    assert reader.int32() == -42 and reader.uint32() == 0xFFFFFFFF
    assert reader.int64() == -(1 << 40) and reader.double() == 1.5
    assert reader.fixed(16) == b"\x01" * 16 and reader.string() == "salom"
    assert reader.bytes() == b"x" * 300 and reader.remaining == 0
    with pytest.raises(TLDecodeError):
        reader.int32()
    with pytest.raises(ValueError):
        TLWriter().fixed(b"short", 16)
    with pytest.raises(TypeError):
        TLWriter().bytes("not bytes")  # type: ignore[arg-type]
    assert len(TLWriter().bytes(b"abc")) == 4


def test_object_access_validation_and_repr() -> None:
    message = types.message(id=1, peer_id=types.peerUser(user_id=5), date=0, message="hi", out=True)
    assert message.out is True and message.mentioned is False and message.entities is None
    assert message.get("entities", []) == [] and message.tl_name == "message"
    assert message.to_dict()["peer_id"] == {"_": "peerUser", "user_id": 5}
    assert "message(" in repr(message) and message == types.message(**message.values)
    with pytest.raises(AttributeError):
        _ = message.not_a_field
    with pytest.raises(TypeError, match="missing"):
        types.message(id=1)
    with pytest.raises(TypeError, match="unknown"):
        types.peerUser(user_id=1, extra=2)
    assert types.user(id=1, self=True).self is True


def test_round_trip_with_flags_vectors_and_bool() -> None:
    message = types.message(
        id=7,
        peer_id=types.peerChannel(channel_id=99),
        date=1,
        message="salom",
        silent=True,
        views=10,
        forwards=2,
        entities=[types.messageEntityBold(offset=0, length=5)],
    )
    decoded = SERIALIZER.deserialize(SERIALIZER.serialize(message))
    assert decoded == message and decoded.silent and decoded.views == 10
    request = functions.messages.getHistory(
        peer=types.inputPeerSelf(),
        offset_id=0,
        offset_date=0,
        add_offset=0,
        limit=5,
        max_id=0,
        min_id=0,
        hash=0,
    )
    assert SERIALIZER.deserialize(SERIALIZER.serialize(request)) == request


def test_bool_vectors_and_gzip() -> None:
    assert SERIALIZER.deserialize(struct.pack("<I", 0x997275B5)) is True
    long_vector = TLWriter().uint32(0x1CB5C415).int32(2).int64(5).int64(-6).to_bytes()
    assert SERIALIZER.deserialize(long_vector, parse_type("Vector<long>")) == [5, -6]
    packed = SERIALIZER.serialize(types.peerUser(user_id=3))
    gzipped = TLWriter().uint32(0x3072CFA1).bytes(gzip.compress(packed)).to_bytes()
    assert SERIALIZER.deserialize(gzipped) == types.peerUser(user_id=3)
    with pytest.raises(TLDecodeError, match="Unknown constructor"):
        SERIALIZER.deserialize(struct.pack("<I", 0x12345678))


def test_type_errors_name_the_field() -> None:
    bad_peer = functions.messages.sendMessage(peer=types.inputUserSelf(), message="x", random_id=1)
    with pytest.raises(TLTypeError, match=r"messages\.sendMessage\.peer: expected InputPeer"):
        SERIALIZER.serialize(bad_peer)
    bad_int = types.peerUser(user_id="nope")
    with pytest.raises(TLTypeError, match=r"peerUser\.user_id"):
        SERIALIZER.serialize(bad_int)
    with pytest.raises(TLTypeError, match="expected a list"):
        SERIALIZER.serialize(functions.users.getUsers(id="me"))


def test_shared_flag_bits_require_every_field() -> None:
    # `bot:flags.14?true` and `bot_info_version:flags.14?int` share one bit.
    with pytest.raises(TLTypeError, match=r"user\.bot_info_version is required when its flag"):
        SERIALIZER.serialize(types.user(id=1, bot=True))
    complete = types.user(id=1, bot=True, bot_info_version=3)
    decoded = SERIALIZER.deserialize(SERIALIZER.serialize(complete))
    assert decoded.bot is True and decoded.bot_info_version == 3
    plain = SERIALIZER.deserialize(SERIALIZER.serialize(types.user(id=1)))
    assert plain.bot is False and plain.bot_info_version is None


def test_result_type_unwraps_generic_wrappers() -> None:
    wrapped = functions.invokeWithLayer(
        layer=1,
        query=functions.initConnection(
            api_id=1,
            device_model="d",
            system_version="s",
            app_version="a",
            system_lang_code="en",
            lang_pack="",
            lang_code="en",
            query=functions.users.getUsers(id=[types.inputUserSelf()]),
        ),
    )
    assert str(SERIALIZER.result_type(wrapped)) == "Vector<User>"


def test_namespaces() -> None:
    assert "messages" in dir(functions) and "sendMessage" in dir(functions.messages)
    assert repr(functions.messages) == "<TLNamespace functions.messages>"
    assert functions.help.getConfig.tl_id == 0xC4F9186B
    assert "TLConstructor" in repr(functions.help.getConfig)
    with pytest.raises(AttributeError):
        _ = functions.messages.notAMethod
    with pytest.raises(AttributeError):
        _ = types._private


def test_tl_object_is_function_flag() -> None:
    assert functions.help.getConfig().is_function
    assert not types.inputPeerSelf().is_function
    assert isinstance(types.inputPeerSelf(), TLObject)
