use pyo3::prelude::*;

/// Return the `opscli-core` crate version compiled into this extension.
#[pyfunction]
fn rust_core_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

/// Native extension imported by Python as `opscli._native`.
#[pymodule]
#[pyo3(name = "_native")]
fn opscli_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(rust_core_version, module)?)?;
    Ok(())
}
