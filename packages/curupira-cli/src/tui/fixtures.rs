//! Sample sessions for rendering and interaction tests.

use super::app::{Conversation, Entry, Session, SessionStatus};

fn user(text: &str) -> Entry {
    Entry::User(text.into())
}

fn agent(name: &str, text: &str) -> Entry {
    Entry::Agent {
        name: name.into(),
        text: text.into(),
    }
}

fn code(lang: &str, source: &str) -> Entry {
    Entry::Code {
        lang: lang.into(),
        lines: source.lines().map(str::to_owned).collect(),
    }
}

fn session(repository: &str, name: &str, agent: &str, entries: Vec<Entry>) -> Session {
    Session {
        key: format!("test:{name}"),
        repository: repository.into(),
        name: name.into(),
        agent: agent.into(),
        status: SessionStatus::Running,
        conversation: Conversation::new(entries),
    }
}

/// Aliases registered in the sample settings. `docs` has no session.
#[must_use]
pub fn repositories() -> Vec<String> {
    vec!["api".into(), "web".into(), "docs".into()]
}

#[must_use]
pub fn sessions() -> Vec<Session> {
    vec![
        session(
            "api",
            "Login Feature",
            "Cursor",
            vec![
                user("Please implement a JWT authentication endpoint."),
                agent(
                    "Cursor",
                    "Let me generate the route. Tokens are signed with JWT_SECRET from the environment.",
                ),
                code(
                    "js",
                    r#"const jwt = require("jsonwebtoken");

router.post("/login", async (req, res) => {
  const user = await users.verify(req.body);
  if (!user) return res.status(401).end();
  const token = jwt.sign({ sub: user.id }, process.env.JWT_SECRET, { expiresIn: "1h" });
  res.json({ token });
});"#,
                ),
                agent(
                    "Cursor",
                    "Added the route to src/routes/auth.js. Want a refresh-token flow as well?",
                ),
                user("Yes. Keep refresh tokens in an httpOnly cookie."),
                agent(
                    "Cursor",
                    "Updating the cookie options and adding a /refresh handler next to /login.",
                ),
                code(
                    "js",
                    r#"res.cookie("refresh", refresh, {
  httpOnly: true,
  sameSite: "strict",
  maxAge: 7 * 24 * 3600 * 1000,
});"#,
                ),
                agent(
                    "Cursor",
                    "Both handlers share one signing helper, so rotating the secret stays a one-line change.",
                ),
            ],
        ),
        session(
            "api",
            "Auth Test",
            "Codegen-01",
            vec![
                user("Write tests for the login endpoint, including an expired token."),
                agent(
                    "Codegen-01",
                    "Here is the suite I am adding to tests/auth.test.js:",
                ),
                code(
                    "js",
                    r#"describe("POST /login", () => {
  it("rejects a bad password", async () => {
    const res = await request(app).post("/login").send({ email, password: "nope" });
    expect(res.status).toBe(401);
  });
});"#,
                ),
                agent(
                    "Codegen-01",
                    "3 of 4 cases pass. The expired-token case fails because the clock is not mocked yet.",
                ),
            ],
        ),
        session(
            "web",
            "DB Migration",
            "Claude-3",
            vec![
                user("Add a last_login_at column to users without locking the table."),
                agent(
                    "Claude-3",
                    "Postgres adds a nullable column without rewriting the table. The migration:",
                ),
                code(
                    "sql",
                    r"-- 20261018_add_last_login_at.sql
ALTER TABLE users
  ADD COLUMN last_login_at TIMESTAMPTZ NULL;

CREATE INDEX CONCURRENTLY idx_users_last_login
  ON users (last_login_at);",
                ),
                agent(
                    "Claude-3",
                    "CREATE INDEX CONCURRENTLY cannot run inside a transaction, so it gets its own migration.",
                ),
            ],
        ),
    ]
}
