Optional dependencies

- pypowsybl (provides SLD raw generation and IIDM features)
  - This package may not have pre-built wheels for aarch64 and may fail to install on this platform.
  - It is now placed in `requirements_optional.txt` and will be attempted during deploy as an optional install; failure will not block deployment.
  - If you need full SLD features on x86_64 or other supported platforms, install manually: `pip install pypowsybl`.
