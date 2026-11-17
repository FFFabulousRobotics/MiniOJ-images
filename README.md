# MiniOJ images

Reusable container images for MiniOJ. The images contain the toolchain and the
MiniOJ package from PyPI. Course projects, student code, judge configuration,
and GitHub credentials are supplied by the calling workflow.

## Java 21 image

| Component | Version |
| --- | --- |
| JDK | 21, provided by the Gradle base image |
| Gradle | 9.1.0 |
| MiniOJ | latest from PyPI |

This image publishes to `ghcr.io/fffabulousrobotics/minioj-java21`.

The image starts `minioj` directly, with `/workspace` as its working directory.
With no arguments, it displays CLI help. Gradle is installed on `PATH`, so build
stages should call `gradle`, using `--offline` when networking is disabled.
There is no Gradle Wrapper download or cache reconstruction at startup.

## Reuse the PR workflow

This repository also provides `.github/workflows/judge.yml`, which runs judging
and comment publication in separate jobs. A student repository needs only this
caller workflow:

```yaml
name: Test on MiniOJ
on:
  issue_comment:
    types: [created, edited]
permissions:
  contents: read
  packages: read
concurrency:
  group: minioj-${{ github.event.issue.number }}
  cancel-in-progress: true
jobs:
  minioj:
    if: >-
      github.event.issue.pull_request &&
      contains(github.event.comment.body, '@minioj-bot') &&
      github.event.repository.fork == false
    uses: FFFabulousRobotics/MiniOJ-images/.github/workflows/judge.yml@v1.0.0
    secrets:
      MINIOJ_CLIENT_ID: ${{ secrets.MINIOJ_CLIENT_ID }}
      MINIOJ_PRIVATE_KEY: ${{ secrets.MINIOJ_PRIVATE_KEY }}
```

The reusable workflow checks out the calling repository's default branch and PR,
assembles the writable project, renames the wrapper property files, pulls the
image, runs MiniOJ, and saves the complete feedback artifact. Its second job
publishes the feedback to the calling PR. The container receives no credentials.
The caller owns the comment trigger and concurrency policy.

Optional inputs are `image` (default: the image in the table above) and
`config-repository` (default: `MiniOJ-config`, a repository name under the caller's
owner). The GitHub App must have access to the calling repository and that
configuration repository. Only the two named App secrets are forwarded.

## Build and verify locally

From this repository, on a Linux host with Docker and Python 3:

```sh
docker build -f java21/Dockerfile -t minioj-java21:local .
python3 tests/smoke.py --image minioj-java21:local
```

The smoke check builds and runs an executable JAR through MiniOJ, writes a
Markdown feedback file, and verifies output ownership. It also checks that a
compilation failure removes the previous JAR and that infinite loops time out.
Gradle builds and execution happen with container networking disabled.

## Use a writable project mount

Create the grading workspace on the runner before starting the container. In
`FTCCodingExercises`, the workflow combines default-branch Gradle files with the
PR's `Main.java` files. The image contains no course files and does not copy or
modify the checkout at startup.

For an existing `project/` and `config/` directory:

```sh
docker run --rm --network none --cap-drop ALL \
  --security-opt no-new-privileges --read-only \
  --memory 1g --cpus 2 --pids-limit 256 \
  --user "$(id -u):$(id -g)" \
  --tmpfs /tmp:rw,exec,nosuid,nodev,size=512m \
  --mount "type=bind,src=$PWD/project,dst=/workspace" \
  --mount "type=bind,src=$PWD/config,dst=/config,readonly" \
  ghcr.io/fffabulousrobotics/minioj-java21:1.0.0 \
  --config /config --comment '@minioj-bot run w1/ex1' \
  --output /workspace/feedback.md
```

The read-write `/workspace` mount holds Gradle's project cache and build outputs.
The image sets `GRADLE_USER_HOME=/tmp/gradle-home` for its writable user cache.
Matching the host UID/GID keeps generated files owned by the runner and requires
no sudo or recursive ownership changes. The root filesystem can remain read-only.

The consumer workflow keeps GitHub posting in a separate job. MiniOJ only writes
Markdown and receives no GitHub token.

## Publish to GHCR

Create `FFFabulousRobotics/MiniOJ-images` on GitHub and push this local repository
to it. The `Test images`
workflow builds and tests changes on `main` and pull requests.

To publish the image, push a `vX.Y.Z` tag after committing the files:

```sh
git tag vX.Y.Z
git push origin vX.Y.Z
```

Alternatively, run `Publish images` manually with `image_tag` set to `X.Y.Z`.
The workflow builds and tests the image before publishing it with the repository's
`GITHUB_TOKEN` and `packages: write` permission. The image is labeled with the
source repository and commit.

Maintainers should grant
`FFFabulousRobotics/FTCCodingExercises` read access under the package's
**Manage Actions access** settings. The consumer workflow logs in with its
`GITHUB_TOKEN`, which has `packages: read` permission.

When updating tools, change the Dockerfile defaults and smoke-check expectations,
publish a new image release, then update the reusable workflow's default image
and the source ref used by callers. A caller can override the image with the
`image` input.