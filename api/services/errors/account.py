"""账户相关领域异常（由路由层映射为 HTTP 状态码）。"""


class AccountPasswordError(Exception):
    """邮箱或密码错误、未设置密码等。"""


class AccountLoginError(Exception):
    """账户禁止登录（如封禁）。"""


class AccountAlreadyExistsError(Exception):
    """邮箱已注册。"""


class AccountRefreshTokenError(Exception):
    """Refresh 无效或已过期。"""
