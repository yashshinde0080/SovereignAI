// build.rs
fn main() {
    println!("cargo:rerun-if-changed=inference_engine/");
    println!("cargo:rerun-if-changed=configs/");

    #[cfg(target_os = "windows")]
    {
        println!("cargo:rustc-link-lib=static=inference_engine");
        println!("cargo:rustc-link-search=native=inference_engine/build/Release");
    }

    #[cfg(not(target_os = "windows"))]
    {
        println!("cargo:rustc-link-lib=static=inference_engine");
        println!("cargo:rustc-link-search=native=inference_engine/build");
    }
}