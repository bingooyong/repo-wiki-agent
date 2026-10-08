"""Role prompts and output-tool schemas. Evidence is always passed as flat strings
(``'FILE:LINE: exact quote'``): long nested object arrays are emitted corrupted by some models.

Keep templates stable: every byte is part of the cassette key.
"""

from __future__ import annotations

from repo_wiki.agent_loop.tools import fn

EVID_STR = {
    "type": "array",
    "items": {"type": "string", "description": "'FILE:LINE: exact quote copied from that line'"},
}
STR_LIST = {"type": "array", "items": {"type": "string"}}

# ------------------------------------------------------------------ recognizer
SUBMIT_PROFILE = fn(
    "submit_profile",
    "Submit the repository profile. Every framework and entry point needs evidence.",
    {
        "languages": STR_LIST,
        "frameworks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "evidence": EVID_STR},
            },
        },
        "entry_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "role": {"type": "string"},
                    "evidence": EVID_STR,
                },
            },
        },
        "layout": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"dir": {"type": "string"}, "purpose": {"type": "string"}},
            },
        },
    },
    ["languages", "frameworks", "entry_points"],
)
ROLE_RECOGNIZE = """You are the Recognizer in a documentation agent. Build a factual profile of this repository:
languages, web/app frameworks, entry points (files that create/start the application), and top-level layout.
Use the tools; every framework and entry point must carry evidence ('FILE:LINE: exact quote copied from that line').
Manifests tell you dependencies; confirm the framework by the import/constructor in source. Be economical, then call submit_profile."""

# ------------------------------------------------------------------ fact pages
RECORD_FACTS = fn(
    "record_facts",
    "Record facts you CONFIRMED in source (appends; at most 10 per call). The program verifies each one "
    "immediately and answers with accepted/rejected + reasons. ONE FACT PER STRING, fields separated by ' | ':\n"
    "'<checklist id> | <slot> | <value> | <claim in Chinese> | FILE:LINE: exact quote || FILE:LINE: exact quote'",
    {
        "facts": {
            "type": "array",
            "items": {
                "type": "string",
                "description": "'item | slot | value | claim | FILE:LINE: exact quote || FILE:LINE: exact quote' "
                "— value must appear in the evidence lines; every identifier/number/path in the claim must "
                "appear in the evidence lines",
            },
        }
    },
    ["facts"],
)
DISMISS = fn(
    "dismiss",
    "Mark inventory items that do not belong on this page, each with a reason (e.g. test helper, duplicate of "
    "another definition, not persisted, CI-only). ONE ITEM PER STRING: '<inventory key exactly as listed> | <reason>'.",
    {"items": {"type": "array", "items": {"type": "string", "description": "'KEY | reason'"}}},
    ["items"],
)
FINISH = fn(
    "finish",
    "Finish. List checklist ids you could not confirm as '<id>: what is missing'.",
    {"unresolved": STR_LIST},
    [],
)
SUBMIT_AUDIT = fn(
    "submit_audit",
    "Submit audit findings. 'wrong'/'omission' MUST carry source evidence ('FILE:LINE: exact quote'); "
    "'invented' MUST quote the page text. Every 'wrong' finding MUST name the disputed fact in fact_id (the [Fn] the page "
    "cites for that statement); several ids may be given comma-separated.",
    {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["invented", "omission", "wrong"]},
                    "severity": {"type": "string", "enum": ["high", "low"]},
                    "fact_id": {
                        "type": "string",
                        "description": "id(s) of the disputed fact(s), e.g. 'F7' or 'F7,F9' (required for 'wrong')",
                    },
                    "page_quote": {"type": "string"},
                    "detail": {"type": "string"},
                    "ev": EVID_STR,
                },
                "required": ["type", "detail"],
            },
        },
        "verdict": {"type": "string", "enum": ["pass", "fail"]},
    },
    ["findings", "verdict"],
)

ROLE_SHARD = """You are an Investigator for ONE shard of a documentation page ("{title}"). Reader question: {question}
Record, with record_facts, every fact in your shard that answers the checklist; account for every listed inventory item: an item is
accounted if a recorded fact cites its line (+-3) (modules: a 'module' fact whose value is that directory), or you dismiss it with a reason.
Slots: {slots}.
Rules:
- record_facts takes one string per fact: 'item | slot | value | claim | FILE:LINE: exact quote || FILE:LINE: exact quote';
  evidence is text copied from that line; value must literally appear in the evidence lines.
- source/config beats docs. README text proves only what the README states (documented commands, documented requirements); a
  directory's role must be proven by code inside that directory, not by a README tree.
- claims are one Chinese sentence; every identifier, path, number, version or command in a claim must appear in the evidence lines.
  Never write conventions, guesses or behaviour you have not read.
- keep the source's own label: describe a value with the words its source line uses (e.g. a URL the source calls the server
  address is not a docs URL); a computed/derived object (view, join result, response/aggregate type) is not a stored table.
- when two sources disagree (docs vs code default, doc path vs flag default), record BOTH and a 'conflict' fact citing both lines.
- a checklist item that genuinely does not apply: record a 'note' fact (value = the checklist id) with evidence showing why.
- record_facts answers immediately with the program's verdict; fix and re-record rejected facts in your next turn.
- you get an OUTLINE, not whole files; read narrow ranges only when needed. When the outline suffices, record, dismiss and finish
  in the SAME turn. Strict tool budget."""
ROLE_GAP = """You are the Gap Investigator for the page "{title}". Reader question: {question}
Some checklist items have no verified fact yet. Using the tools, establish them from source with record_facts (same evidence rules:
'FILE:LINE: exact quote', value literally in evidence, claim tokens grounded), or list them in finish(unresolved) when the repository
does not contain the answer (e.g. no version declared). Slots: {slots}. Strict tool budget."""
ROLE_WRITER = """You are the Writer of the page "{title}" (Chinese Markdown). Use ONLY the verified facts given. Rules:
- structure the page with '## ' section headings; do not write a '# ' title or a table of contents (the program adds both).
- every factual sentence/bullet ends with the ids of the facts it relies on, like [F3].
- do not add any name, path, command, port, version, variable, file or behaviour that is not in the verified facts; do not
  generalise (a fact about one component/listener/environment must not be stated for another).
- code blocks may only contain command lines copied verbatim from 'command' facts (one per line, no added comments or flags).
- the program renders {tables} and inserts it where you write the line {placeholder} (write that line exactly once); do not
  duplicate that content in your own tables.
- use each source's own label for a value (the fact's quote shows it); never relabel (e.g. a server address as a docs URL).
- 'conflict' facts are shown by the program in a 来源不一致 section; never present only one side of a conflict as the answer.
- never present a computed/derived object (view, join, response/aggregate type) as a stored table.
- only for items listed under 'Unresolved checklist items' write one short line “未能从源码确认：<item>”; never add such lines for anything else.
- concise and useful, ordered for the reader; no meta talk. Output only the page."""
ROLE_AUDITOR = """You are the Auditor, an adversarial reviewer of the page "{title}". You start with a fresh context: verify
the page against the repository with the tools, not against your expectations. Hunt for:
(1) invented claims — anything in the page not supported by the verified facts or the source;
(2) wrong facts — page statements or verified facts the source contradicts, including over-generalisation (a statement about one
    component, listener, binary, environment or config mode stated as if it applied to another or to all) — check the code path;
(3) omissions — go through EVERY checklist id and look in the source for facts that answer it but are missing from the page
    (versions, required variables, alternative run modes, routes, tables, fields, modules) — report them as 'omission' with high severity;
(4) labels that contradict their source line (e.g. a URL called a docs URL when the source calls it the server address), and
    doc-vs-code disagreements shown with one side only.
Unsupported page text with no fact id counts as 'invented'. A true but incomplete statement (a role described too narrowly,
a list that misses items) is an 'omission', NOT 'wrong' — 'wrong' means the source contradicts it.
'wrong'/'omission' findings MUST carry evidence ('FILE:LINE: exact quote'); 'invented' MUST quote the page text; every 'wrong'
finding MUST give fact_id = the [Fn] the page cites for the disputed statement. Report nothing you cannot support. Strict tool budget; then call submit_audit."""

# ------------------------------------------------------------------ API page
DERIVE_HELP = (
    "Example of a derived part: 'items @ pkg/x.go:120 <= HandleItems | strip_prefix:Handle,lower'. Allowed derive ops "
    "(applied left to right to source_text): lower, upper, snake, kebab, strip_prefix:<s>, strip_suffix:<s>, add_prefix:<s>, "
    "add_suffix:<s>; for a METHOD derived from a name also end with ends_with_method or starts_with_method (checked "
    "case-insensitively)."
)
RECORD_ROUTES = fn(
    "record_routes",
    "Record HTTP routes you CONFIRMED (appends; at most 12 routes per call, call again for more). "
    "Evidence strings: 'VALUE @ FILE:LINE' when VALUE is literally on that line (+-3 lines), or "
    "'VALUE @ FILE:LINE <= SOURCE_TEXT | op1,op2' when VALUE is derived from SOURCE_TEXT (a short exact token on that line, "
    "e.g. a function/type/field name or tag value - not the whole line). " + DERIVE_HELP,
    {
        "routes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "GET/POST/PUT/PATCH/DELETE/OPTIONS/HEAD, or ANY when every method is accepted",
                    },
                    "path": {"type": "string", "description": "full path = parts joined"},
                    "method_ev": {
                        "type": "string",
                        "description": "'FILE:LINE' where the method literal is, or 'FILE:LINE <= SOURCE_TEXT | ops,ends_with_method'",
                    },
                    "parts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "ordered outermost prefix -> local path; each 'VALUE @ FILE:LINE' or "
                        "'VALUE @ FILE:LINE <= SOURCE_TEXT | ops'",
                    },
                    "handler": {"type": "string"},
                },
                "required": ["method", "path", "method_ev", "parts"],
            },
        }
    },
    ["routes"],
)
DISMISS_SITES = fn(
    "dismiss_sites",
    "Mark candidate sites that are NOT server route registrations (client calls, tests, string utilities, docs; "
    "debug-only listeners are still routes!). ONE SITE PER STRING: 'FILE:LINE | reason'.",
    {
        "sites": {
            "type": "array",
            "items": {"type": "string", "description": "'FILE:LINE | reason'"},
        }
    },
    ["sites"],
)
FINISH_NOTES = fn("finish", "Finish this task.", {"notes": {"type": "string"}}, [])
FINISH_FACTS = fn(
    "finish",
    "Finish. Every checklist id must end up in exactly one place: a recorded fact, covered_by_routes, or unresolved.",
    {
        "unresolved": {
            "type": "array",
            "items": {"type": "string"},
            "description": "'<id>: <what could not be confirmed>'",
        },
        "covered_by_routes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "ids fully answered by the verified route list itself (paths, methods, handler locations)",
        },
    },
    [],
)
SUBMIT_MECH = fn(
    "submit_mechanisms",
    "Submit the route-registration mechanisms.",
    {
        "mechanisms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "summary": {"type": "string"},
                    "method_rule": {"type": "string"},
                    "path_rule": {"type": "string"},
                    "param_rule": {"type": "string"},
                    "call_site_regex": {
                        "type": "string",
                        "description": "Python regex matching the source lines that register routes via this mechanism",
                    },
                    "evidence": EVID_STR,
                },
                "required": ["id", "summary", "method_rule", "path_rule", "evidence"],
            },
        },
        "servers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "entry_file": {"type": "string"},
                    "notes": {"type": "string"},
                },
            },
        },
    },
    ["mechanisms"],
)
SUBMIT_ATTR = fn(
    "submit_attribution",
    "Assign each registration file to the server/binary whose HTTP listener serves its routes.",
    {
        "assignments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "server": {
                        "type": "string",
                        "description": "exactly one of the given server names",
                    },
                    "evidence": EVID_STR,
                },
                "required": ["file", "server", "evidence"],
            },
        }
    },
    ["assignments"],
)
ROLE_MECH = """You are the Route-Mechanism Analyst of a documentation agent. Before anyone enumerates routes, determine HOW this
codebase registers HTTP routes. Possible mechanisms: direct framework calls, groups/sub-routers/mounts/blueprints with prefixes,
decorators, class-based resources, config- or table-driven registration, custom wrapper/registry functions, and reflection or
naming conventions (paths or methods derived from type/method/field names, struct tags, annotations). For each mechanism state:
how the HTTP method is determined (literal, or derived — exactly which name and which rule), how the full path is composed (which
literal pieces and which transformations), how path parameters are expressed, and a Python regex that matches the source lines
registering routes through it. Read the mechanism's implementation, not just its call sites. Every mechanism needs evidence
('FILE:LINE: exact quote'): its implementation and one usage. If several servers/binaries exist, list them with their entry file.
Be economical (strict tool budget), then call submit_mechanisms."""
ROLE_ROUTE_SHARD = """You are a Route Investigator working on ONE shard of a repository. Using the verified registration mechanisms, record
every HTTP route registered in the shard's files with record_routes, and account for every listed candidate site: a site is
accounted if a recorded route cites that line in method_ev or a path part (or a line within 3 of it whose part value is the
site's literal), or if you dismiss it with dismiss_sites (e.g. client-side request, string utility, test helper, documentation
string). You get a line-numbered OUTLINE, not whole files; use read_file on narrow ranges only for lines the outline lacks. Rules:
- parts go from outermost prefix to local path; each part cites the line of its literal ('VALUE @ FILE:LINE'). If a piece is
  DERIVED (e.g. from a method/type/field name or tag), cite 'VALUE @ FILE:LINE <= SOURCE_TEXT | ops' where SOURCE_TEXT is the short
  exact token on that line, so a program can recompute VALUE.
- the method must be literal at method_ev, or derived ('FILE:LINE <= TOKEN | ops,ends_with_method'); ANY only when the
  mechanism accepts every method: cite the accept-all registration line, or - for name-derived methods - the token and ops showing
  that no method matches. Never guess a method.
- record_routes answers immediately with the program's verification result; fix and re-record rejected routes in your next turn.
- at most 12 routes per record_routes call; make several calls in the same turn if needed.
- prefixes coming from elsewhere (mounts, groups, base paths) must cite their own literal lines.
- record nothing you have not seen in source. When the outline suffices, record all routes, dismiss non-route sites and call
  finish in the SAME turn."""
ROLE_ATTR = """You are the Server-Attribution Investigator. A repository can run several HTTP servers (binaries, listeners). For each
registration file, determine which server's listener actually serves the routes registered there, by following the call chain from
the server's entry file to the code that builds or mounts that router (imports, constructor calls, init-time registries, the handler
passed to the listener). Cite evidence lines ('FILE:LINE: exact quote'). If a file's routes are served by a separate debug/auxiliary
listener inside a server process, name that server and say so in the quote context. Use only the given server names; omit a file
you cannot link with evidence. Strict tool budget; then call submit_attribution."""
ROLE_API_FACTS = """You are the Investigator for the non-route facts of an API reference page. The HTTP routes are already established
(summary given); checklist items answered by the route list itself go into finish(covered_by_routes). Establish the remaining
checklist items (server/listen address, authentication, request/response conventions) from source with record_facts, using the
same flat-string format and evidence rules: '<checklist id> | <slot> | <value> | <claim in Chinese> | FILE:LINE: exact quote'.
Slots: {slots}. List what you cannot confirm in finish(unresolved). Never record conventional or guessed facts. Strict tool budget."""
ROLE_API_WRITER = """You are the Writer. Write the PROSE of an API reference page in Chinese Markdown using ONLY the verified facts.
A complete route table is rendered by a program from the verified routes and inserted where you write the line {{ROUTE_TABLE}}
(write that line exactly once). Rules:
- structure the page with '## ' section headings; do not write a '# ' title or a table of contents (the program adds both).
- every factual sentence or bullet ends with the ids of the facts it relies on, like [F3] or [R2]; group-level statements may cite
  one representative [R] id.
- do not add any name, path, command, port, header, version or behaviour that is not in the verified facts; HTTP paths may only be
  verified routes or their prefixes.
- only for items listed under 'Unresolved checklist items' write one short line “未能从源码确认：<item>”.
- routes are grouped by server; state each server's routes and counts separately and never attribute a route to a server other
  than the one given for it.
- 'conflict' facts are shown by the program in a 来源不一致 section; never present only one side of a conflict.
- do not write your own route tables or long route lists; describe groups, auth and conventions. No meta talk. Output only the page."""
