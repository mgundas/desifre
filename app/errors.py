"""Uygulama hataları. Mesajlar kullanıcıya gösterilir, bu yüzden Türkçedir."""


class UserError(Exception):
    """Kullanıcıya olduğu gibi gösterilebilecek hata."""


class Cancelled(Exception):
    """İş kullanıcı tarafından iptal edildi."""
