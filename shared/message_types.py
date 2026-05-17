"""
Canonical message type constants and VERSION shared by server and client.
"""
from __future__ import annotations

VERSION = "0.2.0"


# ── Client → Server ──────────────────────────────────────────────────────────

class C2S:
    AUTH          = "auth"
    JOIN          = "join"
    LEAVE         = "leave"
    MESSAGE       = "message"
    NICK          = "nick"
    CREATE        = "create"
    LIST_CHANNELS = "list_channels"
    LIST_MEMBERS  = "list_members"
    PING          = "ping"
    VOICE_JOIN    = "voice_join"
    VOICE_LEAVE   = "voice_leave"
    VOICE_OFFER   = "voice_offer"
    VOICE_ANSWER  = "voice_answer"
    VOICE_ICE     = "voice_ice"
    PIN_MESSAGE      = "pin_message"
    UNPIN_MESSAGE    = "unpin_message"
    CHANGE_PASSWORD  = "change_password"


# ── Server → Client ──────────────────────────────────────────────────────────

class S2C:
    AUTH_OK         = "auth_ok"
    AUTH_ERROR      = "auth_error"
    CHANNEL_LIST    = "channel_list"
    JOINED          = "joined"
    LEFT            = "left"
    CHAT            = "chat"
    SYSTEM          = "system"
    NICK_CHANGED    = "nick_changed"
    CHANNEL_CREATED = "channel_created"
    USER_LIST       = "user_list"
    ERROR           = "error"
    PONG            = "pong"
    VOICE_STATE     = "voice_state"
    VOICE_OFFER     = "voice_offer"
    VOICE_ANSWER    = "voice_answer"
    VOICE_ICE       = "voice_ice"
    PIN_ADDED            = "pin_added"
    PASSWORD_CHANGED     = "password_changed"
    PASSWORD_CHANGE_ERROR = "password_change_error"
    USER_ONLINE          = "user_online"
    USER_OFFLINE         = "user_offline"


# ── Auth error reasons ────────────────────────────────────────────────────────

class AuthError:
    USERNAME_TAKEN   = "username_taken"
    INVALID_USERNAME = "invalid_username"
    VERSION_MISMATCH = "version_mismatch"
    WRONG_PASSWORD   = "wrong_password"


# ── Server error codes ────────────────────────────────────────────────────────

class PasswordChangeError:
    WRONG_PASSWORD = "wrong_password"
    TOO_SHORT      = "too_short"
    SAME_PASSWORD  = "same_password"
    AUTH_DISABLED  = "auth_disabled"


class ErrorCode:
    NOT_AUTHENTICATED    = "not_authenticated"
    INVALID_JSON         = "invalid_json"
    UNKNOWN_TYPE         = "unknown_message_type"
    NO_SUCH_CHANNEL      = "no_such_channel"
    CHANNEL_EXISTS       = "channel_exists"
    NICK_TAKEN           = "nick_taken"
    INVALID_CHANNEL_NAME = "invalid_channel_name"
    NOT_A_VOICE_CHANNEL  = "not_a_voice_channel"
