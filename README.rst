botocore
========

This is an asyncio port of botocore.  The content below is from boto/botocore.

-------------------

A low-level interface to a growing number of Amazon Web Services. The
botocore package is the foundation for
`AWS-CLI <https://github.com/aws/aws-cli>`__.

`Documentation <https://botocore.readthedocs.org/en/latest/>`__

**WARNING**

Botocore is currently under a developer preview, and its API is subject
to change prior to a GA (1.0) release.  Until botocore reaches a 1.0 release,
backwards compatibility is not guaranteed. The plan for GA is as follows:

1. Add client interface to botocore.
2. Add pending deprecation warnings to the use of ``Service`` and ``Operation``
   objects.
3. Change the pending deprecation warnings to deprecation warnings.
4. Create a `clients-only <https://github.com/boto/botocore/tree/clients-only>`_
   branch that completely removes ``Service`` and ``Operation`` objects.
5. Merge ``clients-only`` branch to develop branch, and make an alpha
   release of botocore.
6. Make a beta release of botocore.
7. Make GA release of botocore.

The project is currently at step **4**.

