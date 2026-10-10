"""Built-in providers registered through Pluggy.

Each subdirectory is an independent provider package so contributors can add or change
one integration without touching the others. A provider may contribute coding-agent
adapters, triggers, or both through the hooks in ``curupira.hooks``; the core loads them
via ``curupira.manager``.
"""
