---
name: linear
description: Use Symphony's injected linear_graphql tool for raw Linear GraphQL operations during app-server sessions.
---

# Linear GraphQL

Use this skill only inside Symphony app-server sessions where the `linear_graphql` client tool is available. It reuses Symphony's configured Linear auth; do not create ad-hoc shell helpers that expose `LINEAR_API_KEY`.

## Tool input

```json
{
  "query": "query or mutation document",
  "variables": {
    "optional": "GraphQL variables object"
  }
}
```

## Rules

- Send one GraphQL operation per tool call.
- Treat a top-level `errors` array as failure even if the tool call itself succeeds.
- Query only the fields needed for the current operation.
- Resolve state IDs from the issue team before changing state; do not hardcode state IDs.
- Prefer GitHub-specific PR attachments when linking PRs.
- Use one persistent `## Codex Workpad` comment for progress; edit it instead of scattering status comments.

## Common operations

### Query an issue by key

```graphql
query IssueByKey($key: String!) {
  issue(id: $key) {
    id
    identifier
    title
    url
    description
    branchName
    state { id name type }
    project { id name }
    labels { nodes { name } }
    links { nodes { id url title } }
    attachments { nodes { id title url sourceType } }
  }
}
```

### Query comments

```graphql
query IssueComments($id: String!) {
  issue(id: $id) {
    comments(first: 50) {
      nodes { id body resolvedAt createdAt updatedAt }
    }
  }
}
```

### Create or update the workpad comment

```graphql
mutation CreateComment($issueId: String!, $body: String!) {
  commentCreate(input: { issueId: $issueId, body: $body }) {
    success
    comment { id url }
  }
}
```

```graphql
mutation UpdateComment($id: String!, $body: String!) {
  commentUpdate(id: $id, input: { body: $body }) {
    success
    comment { id body }
  }
}
```

### Resolve available workflow states

```graphql
query IssueTeamStates($id: String!) {
  issue(id: $id) {
    id
    team { id key name states { nodes { id name type } } }
  }
}
```

### Move an issue to a state

```graphql
mutation MoveIssueToState($id: String!, $stateId: String!) {
  issueUpdate(id: $id, input: { stateId: $stateId }) {
    success
    issue { id identifier state { id name } }
  }
}
```

### Attach a GitHub PR

```graphql
mutation AttachGitHubPR($issueId: String!, $url: String!, $title: String) {
  attachmentLinkGitHubPR(
    issueId: $issueId
    url: $url
    title: $title
    linkKind: links
  ) {
    success
    attachment { id title url }
  }
}
```

### Discover unfamiliar schema fields

```graphql
query QueryFields {
  __type(name: "Query") { fields { name } }
}
```

```graphql
query MutationFields {
  __type(name: "Mutation") { fields { name } }
}
```
