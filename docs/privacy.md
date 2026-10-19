# privacy and trust

## principles

- your project and your applications are private by default
- nothing you upload is used to train models
- beholder never publishes anything on your behalf

## what is stored

- extracted facts, with pointers to their sources
- uploaded documents and rubrics, until you delete them
- scores, views, and exports you generate

## what is not stored

- cloned repo contents, after extraction (clones live in ephemeral sandboxes and are deleted)
- source code is never quoted in exports unless you ask

## repo access

- read-only by default
- exclude files or folders with `.beholderignore`
- secrets patterns are scanned and redacted before any model call

## shared library

- contributing a rubric to the shared library is opt-in
- only public rubrics can be contributed
- confidential or private materials are never contributed or reused across users
- a contributed lens is reviewed before it becomes a preset

## deletion

- disconnecting a repo deletes its derived data
- deleting a project deletes its facts, views, and exports
- deleting an account deletes everything

## model providers

- zero-retention configurations where available
- inputs are never used by providers for training

## access log

- an audit log of access and exports per project is available to the user
