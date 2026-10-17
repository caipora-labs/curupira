//! Per-user runtime paths and process exclusivity.

use std::fs::{self, File, OpenOptions};
use std::io;
use std::path::{Path, PathBuf};

use fs2::FileExt;

use crate::error::CurupiraError;

/// Return `~/.curupira`.
#[must_use]
pub fn dispatch_home() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".curupira")
}

/// Default settings path.
#[must_use]
pub fn default_config_path() -> PathBuf {
    dispatch_home().join("settings.toml")
}

/// Extensions registry root (`~/.curupira/extensions`).
#[must_use]
pub fn extensions_dir() -> PathBuf {
    dispatch_home().join("extensions")
}

/// Create central state and log directories with private permissions when possible.
pub fn ensure_runtime_directories() -> Result<(), CurupiraError> {
    let home = dispatch_home();
    fs::create_dir_all(&home).map_err(|e| CurupiraError::Runtime(e.to_string()))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = fs::set_permissions(&home, fs::Permissions::from_mode(0o700));
    }
    let logs = home.join("logs");
    fs::create_dir_all(&logs).map_err(|e| CurupiraError::Runtime(e.to_string()))?;
    fs::create_dir_all(logs.join("crashes")).map_err(|e| CurupiraError::Runtime(e.to_string()))?;
    fs::create_dir_all(extensions_dir()).map_err(|e| CurupiraError::Runtime(e.to_string()))?;
    Ok(())
}

/// Exclusive dispatch lock.
pub struct DispatchInstanceLock {
    path: PathBuf,
    file: Option<File>,
}

impl DispatchInstanceLock {
    #[must_use]
    pub fn new(path: PathBuf) -> Self {
        Self { path, file: None }
    }

    pub fn acquire(&mut self) -> Result<(), CurupiraError> {
        if self.file.is_some() {
            return Err(CurupiraError::Runtime(
                "instance lock is already acquired".into(),
            ));
        }
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent).map_err(|e| CurupiraError::Runtime(e.to_string()))?;
        }
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .read(true)
            .open(&self.path)
            .map_err(|e| CurupiraError::Runtime(e.to_string()))?;
        file.try_lock_exclusive().map_err(|e| {
            if e.kind() == io::ErrorKind::WouldBlock || e.raw_os_error() == Some(libc_would_block())
            {
                CurupiraError::Dispatch("another curupira process is already running".into())
            } else {
                CurupiraError::Runtime(e.to_string())
            }
        })?;
        self.file = Some(file);
        Ok(())
    }

    pub fn release(&mut self) {
        // Dropping the File releases the advisory lock on supported platforms.
        self.file = None;
    }
}

impl Drop for DispatchInstanceLock {
    fn drop(&mut self) {
        self.release();
    }
}

#[cfg(unix)]
fn libc_would_block() -> i32 {
    11 // EAGAIN on Linux
}

#[cfg(not(unix))]
fn libc_would_block() -> i32 {
    33
}

/// Ensure parent of default config exists when using the default path.
pub fn prepare_default_config_parent(config: &Path) -> Result<(), CurupiraError> {
    if config == default_config_path() {
        if let Some(parent) = config.parent() {
            fs::create_dir_all(parent).map_err(|e| CurupiraError::Runtime(e.to_string()))?;
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                let _ = fs::set_permissions(parent, fs::Permissions::from_mode(0o700));
            }
        }
    }
    Ok(())
}
