//! The Topcoat reference app for the Proper benchmarks: the same three routes
//! as `benchmarks/app`, over the same SQLite file.
//!
//! ```sh
//! cargo build --release && PORT=8123 ./target/release/proper-bench-topcoat
//! ```
use std::path::PathBuf;

use serde::Serialize;
use toasty::Db;
use topcoat::{
    Result,
    context::{Cx, app_context},
    router::{Compression, Router, RouterBuilderDiscoverExt, content::Json, page, route},
    view::{View, view},
};

#[derive(Debug, toasty::Model)]
#[table = "fortune"]
struct Fortune {
    #[key]
    id: i64,
    message: String,
}

#[tokio::main]
async fn main() {
    let db_path = std::env::var("FORTUNES_DB")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../app/fortunes.db"));
    let db = Db::builder()
        .models(toasty::models!(crate::*))
        .connect(&format!("sqlite://{}", db_path.display()))
        .await
        .unwrap();

    // Compression off, as in the Proper app: bombardier does not ask for it,
    // and the comparison is between frameworks, not codecs.
    let router = Router::builder()
        .discover()
        .app_context(db)
        .compression(Compression::off())
        .build();
    topcoat::start(router).await.unwrap();
}

fn db(cx: &Cx) -> Db {
    app_context::<Db>(cx).clone()
}

#[route(GET "/plaintext")]
async fn plaintext() -> Result<&'static str> {
    Ok("Hello, World!")
}

#[derive(Serialize)]
struct Message {
    message: &'static str,
}

#[route(GET "/json")]
async fn json() -> Result<Json<Message>> {
    Ok(Json(Message { message: "Hello, World!" }))
}

struct Row {
    id: i64,
    message: String,
}

#[page("/fortunes")]
async fn fortunes(cx: &Cx) -> Result<impl View> {
    let mut rows: Vec<Row> = Fortune::all()
        .exec(&mut db(cx))
        .await?
        .into_iter()
        .map(|f| Row { id: f.id, message: f.message })
        .collect();
    rows.push(Row { id: 0, message: "Additional fortune added at request time.".to_string() });
    rows.sort_by(|a, b| a.message.cmp(&b.message));
    Ok(view! {
        <!DOCTYPE html>
        <html>
            <head><title>"Fortunes"</title></head>
            <body>
                <table>
                    <tr><th>"id"</th><th>"message"</th></tr>
                    for row in &rows {
                        <tr><td>(row.id)</td><td>(&row.message)</td></tr>
                    }
                </table>
            </body>
        </html>
    })
}
