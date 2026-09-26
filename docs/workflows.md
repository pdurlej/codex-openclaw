[Home](../README.md) · [Documentation](README.md)

# Workflows and example prompts

### Debug OpenClaw with Codex

When your agent behaves differently from what you intended, let Codex compare the
implementation with the agent's account of the behavior. Ask focused questions,
form a hypothesis, make an authorized change, and bring the result back into the
same conversation for feedback.

> My OpenClaw agent keeps producing long answers despite my preference for short
> ones. Inspect the relevant instructions in this project, ask my agent how it
> interprets them, and propose the smallest fix. After the change, run the local
> checks and ask it to respond to the same example again.

**Useful result:** a concrete before/after example, the code or instruction change
behind it, and test evidence. The agent's explanation is a clue to investigate,
not proof of which instructions or runtime path caused the behavior.

### Build and refine personalizations

Use the agent as a feedback partner while Codex develops prompts, skills, response
styles, or workflows. Discuss acceptance examples before implementation, then ask
for feedback on the changed instructions and representative outputs.

> Help me build a concise daily-planning personalization. Ask my OpenClaw agent
> which preferences it already has available, agree on three example requests and
> expected responses, then implement the change in this project. Show the test
> results and ask the agent what still feels unclear or inconsistent.

**Useful result:** explicit examples of what “works for me” means, a tested change,
and a focused list of remaining gaps. A bridge conversation uses a dedicated
session; checking a real channel, scheduled workflow, or deployed installation
still requires exercising that actual path.

### Collaborate on tests and acceptance

Pair a coding agent with an OpenClaw agent that helps personalize your assistant.
Codex can explain a proposed change, ask for edge cases, and return with results.
The OpenClaw agent can challenge assumptions or review examples against the user
context available to it.

> Consult this proposed personalization with my OpenClaw agent. Ask for missing
> acceptance cases and ambiguous behavior. Implement the agreed scope, run the
> relevant tests, then send a concise summary and sample outputs back for review.
> Separate observed test results from the agent's opinions and open questions.

**Useful result:** technical checks plus contextual feedback, together in your
Codex chat. Feedback supports your acceptance decision; an agent saying “looks
right” does not establish that a deployment or user flow passed.

## The feedback loop

1. **Ask:** Codex sends a focused question and the relevant context you authorize.
2. **Collect:** the bridge retrieves the matching answer, attributed to your agent.
3. **Act and check:** Codex uses the feedback in its normal coding and testing work.
4. **Follow up:** continue in the same bridge conversation with results or questions.

This can make iterations easier and potentially cheaper by reducing manual
handoffs and repeated context setup. Cost savings are **not benchmarked or
guaranteed**: both agents still use their configured models, and each new
OpenClaw question can incur the usual provider costs. Start with a small example
and ask targeted follow-ups.

**v1 scope: conversations start in Codex.** The bridge requests consultation from
OpenClaw; it does not provide autonomous OpenClaw-to-Codex messages, wake-ups, or
delegated implementation jobs. Changes and execution remain subject to each
agent's existing permissions. See [Permissions and privacy](reference.md#permissions-and-privacy).

```text
Your Codex chat → question + relevant context → your OpenClaw agent
Your Codex chat ← attributed answer + feedback ← same bridge session
       ↓
  inspect / edit / test → follow-up with results
```

The adapter uses the Python standard library and your existing OpenClaw Gateway.
It needs no remote daemon, public endpoint, token broker, package installation on
the OpenClaw host, or hosted Plugin Creator service. Released under the
[MIT license](../LICENSE).

