<!-- SPDX-License-Identifier: MIT -->

# Release checklist

Use this checklist for each module release. Keep the reusable source unchecked;
record release-specific decisions, identities, results, and exceptions in the
execution chat or release review. Completing a checkbox does not authorize a
Git operation, publication, installation, module administration, GPIO, or RF work.

## Readiness

- [ ] Review the [module contract](../contracts/rp1-gpclk-dkms-module-contract.md),
  intended release scope, compatibility limits, and known issues. Confirm that
  documentation describes current behavior without unsupported promises.
- [ ] Confirm the intended product and Debian packaging identities in the
  canonical header under the [version policy](../contracts/versioning.md).
  Confirm tag, module, DKMS, package, route, UAPI, and metadata identities agree
  where required; independent interface versions retain their own contracts.
- [ ] Select one reviewed, clean source commit from the canonical repository.
  Preserve unrelated work; obtain separate authorization for any required
  staging, commit, push, or tag operation. Record the exact commit and tree.
- [ ] Require passing applicable Linux offline, package, lifecycle, documentation,
  and representative-header checks for that source. Follow
  [testing guidance](../testing.md); inspect runners and record exact results,
  environments, skipped checks, and unresolved failures outside the checkout.
- [ ] Review licensing, source provenance, security implications, and support
  claims. Build compatibility, target administration, timing, waveform, and RF
  qualification remain separate. Require scoped evidence for every claim made.
- [ ] Develop release notes describing the product, significance, WsprryPi use,
  developer integration, operating limits, and documentation links. Keep the
  draft local and excluded from Git until it is used as the GitHub release text.
- [ ] Obtain the explicit user readiness decision for the first stable release.
  Keep module readiness separate from WsprryPi product acceptance.
- [ ] **Merge checkpoint:** obtain explicit authorization and merge the reviewed
  `devel` changes into `main`. Require passing applicable checks on the exact
  resulting `main` commit and record its commit and tree identities. Do not
  begin release artifact preparation until this checkpoint is complete. Build,
  validate, tag, and publish from that same clean source commit; a subsequent
  source change requires affected checks and artifact validation again.

## Artifact preparation and validation

- [ ] Use an identified Linux Debian packaging environment and a new output
  directory outside every source checkout. Record source, toolchain,
  dependencies, architecture, and representative kernel/header identities.
- [ ] Build the intended artifact profile using the
  [preparation procedure](release-candidate.md). For publication-shaped inputs,
  pass `--release` to both the builder and independent validator. Neither tool
  publishes a release or proves publication.
- [ ] Verify the complete seven-artifact set: source archive, Debian package,
  installation manifest, compatibility manifest, release metadata, candidate
  validation metadata, and `SHA256SUMS`. Check public filenames against the
  version policy and inspect package control, payload, modes, and lifecycle inputs.
- [ ] Require successful independent reconstruction and byte-for-byte
  reproducibility checks. Verify checksums, exact source attribution, both UAPI
  identities, overlays, compatibility, and packaged tool identities. Resolve
  validation failures before proceeding.
- [ ] Confirm that prepared metadata retains `published: false` and does not
  invent compatibility entries or qualification. Preparation status and observed
  publication are separate facts.
- [ ] Retain the validated bytes and their digests for publication. Review
  release notes for capabilities, prerequisites, limitations, update/recovery
  guidance, and artifact identity. A change to source or artifacts requires
  affected preparation and validation again.

## Publication

- [ ] Obtain explicit publication authorization for the reviewed source, intended
  tag, release classification, notes, and exact validated artifacts. Resolve an
  existing tag or asset conflict explicitly; do not silently move or replace it.
- [ ] Verify that the intended tag identifies the reviewed source commit. Use
  an ordinary editable GitHub release with the appropriate stable/prerelease
  classification. Do not enable release immutability, tag/asset locks, mandatory
  attestations, or equivalent permanent publication restrictions.
- [ ] Upload the exact validated artifact set, including checksums and provenance
  metadata. Do not rebuild, rewrite metadata, or substitute bytes during upload.
- [ ] Download the published assets and compare every asset with the retained
  validated bytes and digests. Verify repository, tag, source commit, asset names,
  release classification, and consumer-visible URLs. Local `published: false`
  metadata remains unchanged; record observed publication separately.
- [ ] Confirm the published assets pass the independent validator with the
  matching profile and source commit. Resolve publication or download failures
  before declaring the module release available to consumers.

## WsprryPi coordination

- [ ] Supply WsprryPi maintainers with the verified module release tag, source
  commit, asset URLs, checksums, UAPI/interface requirements, compatibility limits,
  and [provider lifecycle contract](../contracts/provider-lifecycle.md).
- [ ] Have WsprryPi explicitly select the verified provider release and check its
  own consumer requirements. Production consumption never follows the moving
  provider default branch; module source is not vendored into the application.
- [ ] Require independent WsprryPi adapter, installer, update/recovery, runtime,
  and product acceptance checks appropriate to its change. Target installation,
  route administration, GPIO, transmission, and RF checks require their own
  authorization and evidence; module CI does not establish those results.
- [ ] Keep GPIO4 and GPIO20 qualification separate. Apply the
  [qualification boundaries](qualification-metadata.md) without transferring
  evidence from another source, route, kernel, waveform, or operating setup.
- [ ] Publish the module before a dependent WsprryPi release. Keep application
  source changes, reviews, commits, publication authorization, release, and
  acceptance decisions independently owned and recorded.
