"""Built-in coding-agent providers.

Each subdirectory is an independent provider package so contributors can add or change
one integration without touching the others. Providers register through Pluggy hooks
defined in ``curupira.hooks``; the core loads them via ``curupira.manager``.
"""
