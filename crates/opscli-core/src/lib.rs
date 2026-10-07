use pyo3::prelude::*;
use pyo3::types::PyTuple;
use std::io::Read;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

/// Return the `opscli-core` crate version compiled into this extension.
#[pyfunction]
fn rust_core_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

/// Run a child process, retaining bounded stdout/stderr tails and killing its process group
/// when the optional timeout expires. This function is called from Python's worker thread.
#[pyfunction]
#[pyo3(signature = (executable, arguments, cwd, timeout, max_output_bytes, capture_output))]
fn run_process(
    executable: &str,
    arguments: &Bound<'_, PyTuple>,
    cwd: Option<&str>,
    timeout: Option<f64>,
    max_output_bytes: usize,
    capture_output: bool,
) -> PyResult<(i32, Vec<u8>, Vec<u8>, bool)> {
    let mut command = Command::new(executable);
    command.args(arguments.iter().map(|arg| arg.extract::<String>()).collect::<PyResult<Vec<_>>>()?);
    command.stdin(Stdio::null());
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
    let mut child = command.spawn().map_err(|error| pyo3::exceptions::PyOSError::new_err(error.to_string()))?;
    let started = Instant::now();
    let mut stdout = Vec::new();
    let mut stderr = Vec::new();
    // Drain both pipes concurrently to avoid deadlock when a child fills either pipe.
    let out = child.stdout.take().map(|mut pipe| std::thread::spawn(move || read_tail(&mut pipe, max_output_bytes)));
    let err = child.stderr.take().map(|mut pipe| std::thread::spawn(move || read_tail(&mut pipe, max_output_bytes)));
    let status = loop {
        if let Some(status) = child.try_wait().map_err(|error| pyo3::exceptions::PyOSError::new_err(error.to_string()))? {
            break status;
        }
        if timeout.is_some_and(|seconds| started.elapsed() >= Duration::from_secs_f64(seconds.max(0.0))) {
            #[cfg(unix)]
            unsafe { kill(-(child.id() as i32), 9); }
            #[cfg(not(unix))]
            { let _ = child.kill(); }
            let _ = child.wait();
            if let Some(worker) = out { let _ = worker.join(); }
            if let Some(worker) = err { let _ = worker.join(); }
            return Err(pyo3::exceptions::PyTimeoutError::new_err("process timed out"));
        }
        std::thread::sleep(Duration::from_millis(5));
    };
    if let Some(worker) = out { stdout = worker.join().map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("stdout reader failed"))?.0; }
    if let Some(worker) = err { stderr = worker.join().map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("stderr reader failed"))?.0; }
    let truncated = (capture_output && max_output_bytes == 0 && (!stdout.is_empty() || !stderr.is_empty()))
        || stdout.len() == max_output_bytes || stderr.len() == max_output_bytes;
    Ok((status.code().unwrap_or(-1), stdout, stderr, truncated))
}

fn read_tail(reader: &mut impl Read, limit: usize) -> (Vec<u8>, bool) {
    let mut output = Vec::new();
    let mut chunk = [0; 16_384];
    let mut truncated = false;
    loop {
        match reader.read(&mut chunk) {
            Ok(0) | Err(_) => break,
            Ok(count) => {
                output.extend_from_slice(&chunk[..count]);
                if output.len() > limit {
                    let excess = output.len() - limit;
                    output.drain(..excess);
                    truncated = true;
                }
            }
        }
    }
    (output, truncated)
}

#[cfg(unix)]
unsafe extern "C" { fn kill(pid: i32, signal: i32) -> i32; }

/// Native extension imported by Python as `opscli._native`.
#[pymodule]
#[pyo3(name = "_native")]
fn opscli_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(rust_core_version, module)?)?;
    module.add_function(wrap_pyfunction!(run_process, module)?)?;
    Ok(())
}
