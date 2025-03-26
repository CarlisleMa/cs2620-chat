# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: chat.proto
# Protobuf Python Version: 5.29.0
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    29,
    0,
    '',
    'chat.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\nchat.proto\x12\x04\x63hat\"\x12\n\x10GetLeaderRequest\"+\n\x11GetLeaderResponse\x12\x16\n\x0eleader_address\x18\x01 \x01(\t\"\x11\n\x0fGetStateRequest\"N\n\x10GetStateResponse\x12\x19\n\x05users\x18\x01 \x03(\x0b\x32\n.chat.User\x12\x1f\n\x08messages\x18\x02 \x03(\x0b\x32\r.chat.Message\"/\n\x04User\x12\x10\n\x08username\x18\x01 \x01(\t\x12\x15\n\rpassword_hash\x18\x02 \x01(\x0c\"o\n\x07Message\x12\n\n\x02id\x18\x01 \x01(\x05\x12\x0e\n\x06sender\x18\x02 \x01(\t\x12\x11\n\trecipient\x18\x03 \x01(\t\x12\x0f\n\x07message\x18\x04 \x01(\t\x12\x11\n\ttimestamp\x18\x05 \x01(\x03\x12\x11\n\tdelivered\x18\x06 \x01(\x05\"*\n\x10HeartbeatRequest\x12\x16\n\x0esender_address\x18\x01 \x01(\t\"$\n\x11HeartbeatResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\")\n\x0f\x45lectionRequest\x12\x16\n\x0esender_address\x18\x01 \x01(\t\"\x1e\n\x10\x45lectionResponse\x12\n\n\x02ok\x18\x01 \x01(\x08\"*\n\x10SetLeaderRequest\x12\x16\n\x0eleader_address\x18\x01 \x01(\t\"$\n\x11SetLeaderResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\"%\n\x10ReplicateRequest\x12\x11\n\toperation\x18\x01 \x01(\t\"$\n\x11ReplicateResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\":\n\x14\x43reateAccountRequest\x12\x10\n\x08username\x18\x01 \x01(\t\x12\x10\n\x08password\x18\x02 \x01(\t\"9\n\x15\x43reateAccountResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t\"2\n\x0cLoginRequest\x12\x10\n\x08username\x18\x01 \x01(\t\x12\x10\n\x08password\x18\x02 \x01(\t\"J\n\rLoginResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t\x12\x17\n\x0funread_messages\x18\x03 \x01(\x05\"!\n\rLogoutRequest\x12\x10\n\x08username\x18\x01 \x01(\t\"2\n\x0eLogoutResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t\"4\n\x13ListAccountsRequest\x12\x0f\n\x07pattern\x18\x01 \x01(\t\x12\x0c\n\x04page\x18\x02 \x01(\x05\"(\n\x14ListAccountsResponse\x12\x10\n\x08\x61\x63\x63ounts\x18\x01 \x03(\t\"A\n\x12SendMessageRequest\x12\x0e\n\x06sender\x18\x01 \x01(\t\x12\n\n\x02to\x18\x02 \x01(\t\x12\x0f\n\x07message\x18\x03 \x01(\t\"7\n\x13SendMessageResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t\"Y\n\x0b\x43hatMessage\x12\n\n\x02id\x18\x01 \x01(\x03\x12\x0e\n\x06sender\x18\x02 \x01(\t\x12\n\n\x02to\x18\x03 \x01(\t\x12\x0f\n\x07message\x18\x04 \x01(\t\x12\x11\n\ttimestamp\x18\x05 \x01(\x03\"6\n\x13ReadMessagesRequest\x12\x10\n\x08username\x18\x01 \x01(\t\x12\r\n\x05\x63ount\x18\x02 \x01(\x05\";\n\x14ReadMessagesResponse\x12#\n\x08messages\x18\x01 \x03(\x0b\x32\x11.chat.ChatMessage\"\'\n\x13ListMessagesRequest\x12\x10\n\x08username\x18\x01 \x01(\t\";\n\x14ListMessagesResponse\x12#\n\x08messages\x18\x01 \x03(\x0b\x32\x11.chat.ChatMessage\">\n\x15\x44\x65leteMessagesRequest\x12\x10\n\x08username\x18\x01 \x01(\t\x12\x13\n\x0bmessage_ids\x18\x02 \x03(\x03\":\n\x16\x44\x65leteMessagesResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t\"(\n\x14\x44\x65leteAccountRequest\x12\x10\n\x08username\x18\x01 \x01(\t\"9\n\x15\x44\x65leteAccountResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t\"$\n\x10SubscribeRequest\x12\x10\n\x08username\x18\x01 \x01(\t2\xa9\x06\n\x0b\x43hatService\x12H\n\rCreateAccount\x12\x1a.chat.CreateAccountRequest\x1a\x1b.chat.CreateAccountResponse\x12\x30\n\x05Login\x12\x12.chat.LoginRequest\x1a\x13.chat.LoginResponse\x12\x33\n\x06Logout\x12\x13.chat.LogoutRequest\x1a\x14.chat.LogoutResponse\x12\x45\n\x0cListAccounts\x12\x19.chat.ListAccountsRequest\x1a\x1a.chat.ListAccountsResponse\x12\x42\n\x0bSendMessage\x12\x18.chat.SendMessageRequest\x1a\x19.chat.SendMessageResponse\x12\x45\n\x0cReadMessages\x12\x19.chat.ReadMessagesRequest\x1a\x1a.chat.ReadMessagesResponse\x12\x45\n\x0cListMessages\x12\x19.chat.ListMessagesRequest\x1a\x1a.chat.ListMessagesResponse\x12K\n\x0e\x44\x65leteMessages\x12\x1b.chat.DeleteMessagesRequest\x1a\x1c.chat.DeleteMessagesResponse\x12H\n\rDeleteAccount\x12\x1a.chat.DeleteAccountRequest\x1a\x1b.chat.DeleteAccountResponse\x12@\n\x11SubscribeMessages\x12\x16.chat.SubscribeRequest\x1a\x11.chat.ChatMessage0\x01\x12<\n\tGetLeader\x12\x16.chat.GetLeaderRequest\x1a\x17.chat.GetLeaderResponse\x12\x39\n\x08GetState\x12\x15.chat.GetStateRequest\x1a\x16.chat.GetStateResponse2\x99\x02\n\x12ReplicationService\x12<\n\tHeartbeat\x12\x16.chat.HeartbeatRequest\x1a\x17.chat.HeartbeatResponse\x12@\n\x0fRequestElection\x12\x15.chat.ElectionRequest\x1a\x16.chat.ElectionResponse\x12<\n\tSetLeader\x12\x16.chat.SetLeaderRequest\x1a\x17.chat.SetLeaderResponse\x12\x45\n\x12ReplicateOperation\x12\x16.chat.ReplicateRequest\x1a\x17.chat.ReplicateResponseb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'chat_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_GETLEADERREQUEST']._serialized_start=20
  _globals['_GETLEADERREQUEST']._serialized_end=38
  _globals['_GETLEADERRESPONSE']._serialized_start=40
  _globals['_GETLEADERRESPONSE']._serialized_end=83
  _globals['_GETSTATEREQUEST']._serialized_start=85
  _globals['_GETSTATEREQUEST']._serialized_end=102
  _globals['_GETSTATERESPONSE']._serialized_start=104
  _globals['_GETSTATERESPONSE']._serialized_end=182
  _globals['_USER']._serialized_start=184
  _globals['_USER']._serialized_end=231
  _globals['_MESSAGE']._serialized_start=233
  _globals['_MESSAGE']._serialized_end=344
  _globals['_HEARTBEATREQUEST']._serialized_start=346
  _globals['_HEARTBEATREQUEST']._serialized_end=388
  _globals['_HEARTBEATRESPONSE']._serialized_start=390
  _globals['_HEARTBEATRESPONSE']._serialized_end=426
  _globals['_ELECTIONREQUEST']._serialized_start=428
  _globals['_ELECTIONREQUEST']._serialized_end=469
  _globals['_ELECTIONRESPONSE']._serialized_start=471
  _globals['_ELECTIONRESPONSE']._serialized_end=501
  _globals['_SETLEADERREQUEST']._serialized_start=503
  _globals['_SETLEADERREQUEST']._serialized_end=545
  _globals['_SETLEADERRESPONSE']._serialized_start=547
  _globals['_SETLEADERRESPONSE']._serialized_end=583
  _globals['_REPLICATEREQUEST']._serialized_start=585
  _globals['_REPLICATEREQUEST']._serialized_end=622
  _globals['_REPLICATERESPONSE']._serialized_start=624
  _globals['_REPLICATERESPONSE']._serialized_end=660
  _globals['_CREATEACCOUNTREQUEST']._serialized_start=662
  _globals['_CREATEACCOUNTREQUEST']._serialized_end=720
  _globals['_CREATEACCOUNTRESPONSE']._serialized_start=722
  _globals['_CREATEACCOUNTRESPONSE']._serialized_end=779
  _globals['_LOGINREQUEST']._serialized_start=781
  _globals['_LOGINREQUEST']._serialized_end=831
  _globals['_LOGINRESPONSE']._serialized_start=833
  _globals['_LOGINRESPONSE']._serialized_end=907
  _globals['_LOGOUTREQUEST']._serialized_start=909
  _globals['_LOGOUTREQUEST']._serialized_end=942
  _globals['_LOGOUTRESPONSE']._serialized_start=944
  _globals['_LOGOUTRESPONSE']._serialized_end=994
  _globals['_LISTACCOUNTSREQUEST']._serialized_start=996
  _globals['_LISTACCOUNTSREQUEST']._serialized_end=1048
  _globals['_LISTACCOUNTSRESPONSE']._serialized_start=1050
  _globals['_LISTACCOUNTSRESPONSE']._serialized_end=1090
  _globals['_SENDMESSAGEREQUEST']._serialized_start=1092
  _globals['_SENDMESSAGEREQUEST']._serialized_end=1157
  _globals['_SENDMESSAGERESPONSE']._serialized_start=1159
  _globals['_SENDMESSAGERESPONSE']._serialized_end=1214
  _globals['_CHATMESSAGE']._serialized_start=1216
  _globals['_CHATMESSAGE']._serialized_end=1305
  _globals['_READMESSAGESREQUEST']._serialized_start=1307
  _globals['_READMESSAGESREQUEST']._serialized_end=1361
  _globals['_READMESSAGESRESPONSE']._serialized_start=1363
  _globals['_READMESSAGESRESPONSE']._serialized_end=1422
  _globals['_LISTMESSAGESREQUEST']._serialized_start=1424
  _globals['_LISTMESSAGESREQUEST']._serialized_end=1463
  _globals['_LISTMESSAGESRESPONSE']._serialized_start=1465
  _globals['_LISTMESSAGESRESPONSE']._serialized_end=1524
  _globals['_DELETEMESSAGESREQUEST']._serialized_start=1526
  _globals['_DELETEMESSAGESREQUEST']._serialized_end=1588
  _globals['_DELETEMESSAGESRESPONSE']._serialized_start=1590
  _globals['_DELETEMESSAGESRESPONSE']._serialized_end=1648
  _globals['_DELETEACCOUNTREQUEST']._serialized_start=1650
  _globals['_DELETEACCOUNTREQUEST']._serialized_end=1690
  _globals['_DELETEACCOUNTRESPONSE']._serialized_start=1692
  _globals['_DELETEACCOUNTRESPONSE']._serialized_end=1749
  _globals['_SUBSCRIBEREQUEST']._serialized_start=1751
  _globals['_SUBSCRIBEREQUEST']._serialized_end=1787
  _globals['_CHATSERVICE']._serialized_start=1790
  _globals['_CHATSERVICE']._serialized_end=2599
  _globals['_REPLICATIONSERVICE']._serialized_start=2602
  _globals['_REPLICATIONSERVICE']._serialized_end=2883
# @@protoc_insertion_point(module_scope)
