use pyo3::exceptions::{PyFileNotFoundError, PyOSError, PyRuntimeError};
use pyo3::prelude::*;
use pyo3::types::PyTuple;
use std::io::Read;
use std::process::{Child, Command, ExitStatus, Stdio};
use std::sync::mpsc::{self, Receiver};
use std::sync::Mutex;
use std::time::Duration;

/// Return the `curupira-core` crate version compiled into this extension.
#[pyfunction]
fn rust_core_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

type ChunkReceiver = Mutex<Receiver<Option<Vec<u8>>>>;

/// A spawned child whose pipes are incrementally drained by native reader threads.
#[pyclass]
struct NativeProcess {
    child: Mutex<Child>,
    stdout: ChunkReceiver,
    stderr: ChunkReceiver,
}

#[pymethods]
impl NativeProcess {
    /// Read the next stdout chunk, or return `None` when stdout is closed.
    fn read_stdout(&self, py: Python<'_>) -> PyResult<Option<Vec<u8>>> {
        py.detach(|| receive_chunk(&self.stdout))
    }

    /// Read the next stderr chunk, or return `None` when stderr is closed.
    fn read_stderr(&self, py: Python<'_>) -> PyResult<Option<Vec<u8>>> {
        py.detach(|| receive_chunk(&self.stderr))
    }

    /// Wait for process termination without holding the GIL.
    fn wait(&self, py: Python<'_>) -> PyResult<i32> {
        py.detach(|| loop {
            let result = self
                .child
                .lock()
                .map_err(|_| PyRuntimeError::new_err("process lock poisoned"))?
                .try_wait()
                .map_err(|error| PyOSError::new_err(error.to_string()))?;
            if let Some(status) = result {
                return Ok(exit_code(status));
            }
            std::thread::sleep(Duration::from_millis(5));
        })
    }

    /// Kill the process group (or the child on non-POSIX systems).
    fn kill(&self) -> PyResult<()> {
        // Windows Child::kill needs &mut self; Unix only reads the pid.
        #[allow(unused_mut)]
        let mut child = self
            .child
            .lock()
            .map_err(|_| PyRuntimeError::new_err("process lock poisoned"))?;
        #[cfg(unix)]
        {
            let result = unsafe { kill(-(child.id() as i32), 9) };
            if result != 0 {
                let error = std::io::Error::last_os_error();
                if error.raw_os_error() != Some(3) {
                    return Err(PyOSError::new_err(error.to_string()));
                }
            }
        }
        #[cfg(not(unix))]
        child
            .kill()
            .map_err(|error| PyOSError::new_err(error.to_string()))?;
        Ok(())
    }
}

impl Drop for NativeProcess {
    fn drop(&mut self) {
        let Ok(mut child) = self.child.lock() else {
            return;
        };
        #[cfg(unix)]
        unsafe {
            kill(-(child.id() as i32), 9);
        }
        #[cfg(not(unix))]
        {
            let _ = child.kill();
        }
        let _ = child.wait();
    }
}

fn receive_chunk(receiver: &ChunkReceiver) -> PyResult<Option<Vec<u8>>> {
    receiver
        .lock()
        .map_err(|_| PyRuntimeError::new_err("pipe reader lock poisoned"))?
        .recv()
        .map_err(|_| PyRuntimeError::new_err("pipe reader stopped unexpectedly"))
}

fn exit_code(status: ExitStatus) -> i32 {
    if let Some(code) = status.code() {
        return code;
    }
    #[cfg(unix)]
    {
        use std::os::unix::process::ExitStatusExt;
        return status.signal().map_or(-1, |signal| -signal);
    }
    #[cfg(not(unix))]
    {
        -1
    }
}

fn reader(pipe: impl Read + Send + 'static) -> Receiver<Option<Vec<u8>>> {
    let (sender, receiver) = mpsc::sync_channel(8);
    std::thread::spawn(move || {
        let mut pipe = pipe;
        let mut buffer = [0; 16_384];
        loop {
            match pipe.read(&mut buffer) {
                Ok(0) | Err(_) => break,
                Ok(size) => {
                    if sender.send(Some(buffer[..size].to_vec())).is_err() {
                        break;
                    }
                }
            }
        }
        let _ = sender.send(None);
    });
    receiver
}

/// Start a supervised process with stdout and stderr either captured or discarded.
#[pyfunction]
#[pyo3(signature = (executable, arguments, cwd, capture_output))]
fn spawn_process(
    executable: &str,
    arguments: &Bound<'_, PyTuple>,
    cwd: Option<&str>,
    capture_output: bool,
) -> PyResult<NativeProcess> {
    let mut command = Command::new(executable);
    let arguments = arguments
        .iter()
        .map(|argument| argument.extract::<String>())
        .collect::<PyResult<Vec<_>>>()?;
    command.args(arguments).stdin(Stdio::null());
    if capture_output {
        command.stdout(Stdio::piped()).stderr(Stdio::piped());
    } else {
        command.stdout(Stdio::null()).stderr(Stdio::null());
    }
    if let Some(directory) = cwd {
        command.current_dir(directory);
    }
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        command.process_group(0);
    }
    let mut child = command.spawn().map_err(|error| {
        if error.kind() == std::io::ErrorKind::NotFound {
            PyFileNotFoundError::new_err(error.to_string())
        } else {
            PyOSError::new_err(error.to_string())
        }
    })?;
    let stdout = match child.stdout.take() {
        Some(pipe) => reader(pipe),
        None => reader(std::io::empty()),
    };
    let stderr = match child.stderr.take() {
        Some(pipe) => reader(pipe),
        None => reader(std::io::empty()),
    };
    Ok(NativeProcess {
        child: Mutex::new(child),
        stdout: Mutex::new(stdout),
        stderr: Mutex::new(stderr),
    })
}

#[cfg(unix)]
unsafe extern "C" {
    fn kill(pid: i32, signal: i32) -> i32;
}

/// Native extension imported by Python as `curupira._native`.
#[pymodule]
#[pyo3(name = "_native")]
fn curupira_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(rust_core_version, module)?)?;
    module.add_function(wrap_pyfunction!(spawn_process, module)?)?;
    module.add_class::<NativeProcess>()?;
    Ok(())
}
