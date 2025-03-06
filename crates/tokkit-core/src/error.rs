use thiserror::Error;

#[derive(Debug, Error)]
pub enum TokkitError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Store error: {0}")]
    Store(String),
    #[error("Parse error: {0}")]
    Parse(String),
    #[error("Pipeline busy — another index is running")]
    PipelineBusy,
    #[error("Project not found: {0}")]
    NotFound(String),
    #[error("{0}")]
    Other(String),
}

pub type Result<T> = std::result::Result<T, TokkitError>;
