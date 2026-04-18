# Protocol Beta Notes

The stable line documents the release-facing protocol concepts:

1. `protocol.hello`
   - declares runtime protocol version
   - exports supported schema versions
   - exports module versions

2. `protocol.negotiate`
   - compares two runtimes
   - reports compatibility
   - reports shared packet schemas

3. `release.manifest`
   - exports the stable release manifest
   - lists modules and protocol metadata
