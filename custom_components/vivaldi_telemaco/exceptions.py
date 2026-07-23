"""Exceptions for Vivaldi Telemaco."""


class TelemacoError(Exception):
    """Base Telemaco error."""


class TelemacoConnectionError(TelemacoError):
    """Device could not be reached."""


class TelemacoAuthenticationError(TelemacoError):
    """Authentication failed."""


class TelemacoProtocolError(TelemacoError):
    """The device returned an unsupported payload."""
