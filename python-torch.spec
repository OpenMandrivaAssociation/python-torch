# Official PyTorch source bundle, compiled here. Never install a
# PyPI manylinux wheel: those are libstdc++ and rpm will not own them.

%undefine _debugsource_packages
# LTO of libtorch_cpu + 1.2G libdnnl OOMs linkers on 64G hosts.
# Imperative build (not declarative python) so CFLAGS are not
# re-injected with flto from distro optflags.
%global _lto_cflags %{nil}
# Strip flto tokens from optflags (no rpm-conditional '?' in sed).
%global torch_cflags %(printf '%%s' '%{optflags}' | sed -e 's/-flto=thin//g' -e 's/-flto//g')

# gfx9xx (Vega20 / MI50 / MI200 / MI300) + RDNA2/3/4.
# Skip gfx803 (Polaris): PyTorch has no real Polaris kernels;
# ggml / hipBLAS still cover RX 550. hipBLASLt only has navi3x/4x.
# Upstream 2.15 wheels drop gfx906. Source builds still accept it
# via PYTORCH_ROCM_ARCH, and MI50 / Radeon VII stay in this list.
%global torch_rocm_arch gfx906;gfx908;gfx90a;gfx942;gfx1030;gfx1100;gfx1101;gfx1102;gfx1200;gfx1201

Name:		python-torch
Version:	2.15.0
Release:	1
Summary:	PyTorch machine learning framework
License:	BSD-3-Clause
Group:		Development/Python
URL:		https://pytorch.org
# Full source bundle from the PyTorch project. The GitHub tag archive
# omits third_party submodules needed to compile.
Source0:	https://github.com/pytorch/pytorch/releases/download/v%{version}/pytorch-v%{version}.tar.gz
# Walks every vendored CK copy (mslk / flash-attn / aiter) after Patch5.
Source1:	pytorch-2.14.0-ck-clang23.py
# LLD rejects BFD-only --stub-group-size. 2.15's prioritized-text
# path already uses --symbol-ordering-file when CMAKE_LINKER_TYPE=LLD
# (set below). This patch only skips the stub-group flag.
Patch0:		pytorch-2.14.0-lld-compat.patch
# TheRock 10.1 has no roctracer libroctx64. ROCTx markers are optional.
Patch1:		pytorch-2.14.0-optional-roctx.patch
# cmake_dependent_option ignores USE_FLASH_ATTENTION=0 from the env
# and downloads prebuilt AOTriton images (no network on ABF).
Patch2:		pytorch-2.14.0-no-aotriton-fetch.patch
# 2.15 still has no USE_SYSTEM_FMT; always builds third_party/fmt.
Patch4:		pytorch-2.14.0-system-fmt.patch
# Clang 23 raw_buffer_* builtins are unsigned; CK still uses int32xN.
# Same class of fix as python-xformers 0001-ck-tile-clang23-rdna.patch.
Patch5:		pytorch-2.14.0-ck-clang23.patch
# FHS ROCM_HOME=/usr must not add -L/usr/lib or -isystem /usr/include.
# /usr/lib/libc.so forces OUTPUT_FORMAT(elf32-i386). -isystem /usr/include
# breaks libstdc++ #include_next.
Patch6:		pytorch-2.14.1-skip-usr-lib.patch

BuildRequires:	python
# find_package(Python COMPONENTS Development.Module) — without
# this cmake silently sets BUILD_PYTHON=OFF and the wheel has no
# torch/_C*.so (xformers 656372: Failed to load PyTorch C extensions).
BuildRequires:	pkgconfig(python3)
BuildRequires:	cmake
BuildRequires:	ninja
BuildRequires:	binutils
# 2.15's PEP 517 backend is scikit-build-core (setup.py is a shim).
BuildRequires:	python%{pyver}dist(scikit-build-core)
BuildRequires:	python%{pyver}dist(setuptools)
BuildRequires:	python%{pyver}dist(wheel)
BuildRequires:	python%{pyver}dist(pip)
BuildRequires:	python%{pyver}dist(packaging)
BuildRequires:	python%{pyver}dist(six)
BuildRequires:	python%{pyver}dist(numpy)
BuildRequires:	python%{pyver}dist(pyyaml)
BuildRequires:	python%{pyver}dist(typing-extensions)
BuildRequires:	python%{pyver}dist(jinja2)
BuildRequires:	python%{pyver}dist(networkx)
BuildRequires:	python%{pyver}dist(sympy)
BuildRequires:	python%{pyver}dist(fsspec)
BuildRequires:	python%{pyver}dist(filelock)
# 2.15 vendors fmt 12; keep the system copy on the same major.
BuildRequires:	cmake(fmt) >= 12

# TheRock 10.1 (FHS /usr, not /opt/rocm). HIP language/ABI is 7.16.
BuildRequires:	hipcc
# clang-linker-wrapper looks this up on PATH; hipcc only Requires clang.
BuildRequires:	/usr/bin/clang-offload-bundler
BuildRequires:	cmake(hip)
BuildRequires:	cmake(hipblas)
BuildRequires:	cmake(rocblas)
BuildRequires:	cmake(miopen)
BuildRequires:	cmake(hipfft)
BuildRequires:	cmake(hiprand)
BuildRequires:	cmake(hipsparse)
BuildRequires:	cmake(hipsolver)
BuildRequires:	cmake(rocsolver)
BuildRequires:	cmake(hipblaslt)
# ROCm >= 7.14 treats hipFile as required. It is packaged.
BuildRequires:	cmake(hipfile)
BuildRequires:	cmake(hiprtc)
BuildRequires:	cmake(hipcub)
BuildRequires:	cmake(rocprim)
BuildRequires:	cmake(rocthrust)
BuildRequires:	cmake(rocrand)
BuildRequires:	cmake(amd_comgr)
BuildRequires:	rocm-runtime-devel
BuildRequires:	cmake(rocm_smi)
# rocm_smi-config.cmake does pkg_check_modules(libdrm REQUIRED).
BuildRequires:	pkgconfig(libdrm)
# c10d/symm_mem/intra_node_comm.cpp includes <amd_smi/amdsmi.h>
BuildRequires:	cmake(amd_smi)
# RCCL is the HIP NCCL. USE_RCCL depends on USE_NCCL; ROCm forces
# USE_SYSTEM_NCCL and find_package(rccl).
BuildRequires:	cmake(rccl)
# Kineto on ROCm 7 links librocprofiler-sdk. The .so lives in lib64;
# find_library still searches the default lib dirs.
BuildRequires:	cmake(rocprofiler-sdk)
# c10d MPI backend. OpenMPI lives under %{_libdir}/openmpi, not PATH.
BuildRequires:	pkgconfig(ompi-cxx)
# ATen Vulkan (desktop): system loader + glslc for shader codegen.
BuildRequires:	pkgconfig(vulkan)
BuildRequires:	glslc

Requires:	python%{pyver}dist(numpy)
Requires:	python%{pyver}dist(typing-extensions) >= 4.13
Requires:	python%{pyver}dist(filelock)
Requires:	python%{pyver}dist(jinja2)
Requires:	python%{pyver}dist(networkx) >= 2.5.1
Requires:	python%{pyver}dist(fsspec) >= 0.8.5
Requires:	python%{pyver}dist(sympy) >= 1.13.3
# Wheel metadata. Used for PEP 639 license expressions, not pkg_resources.
Requires:	python%{pyver}dist(setuptools) >= 77
# c10 / torch.csrc headers include <fmt/...>; cpp_extension builds
# need the system headers (we no longer install bundled fmt).
Requires:	cmake(fmt) >= 12
# HIP/Vulkan .so deps come from the ELF generator. Recommend the
# pieces that are useful at runtime but not always DT_NEEDED.
Recommends:	miopen%{?_isa}
Recommends:	hipblaslt%{?_isa}

%description
Tensors and dynamic neural networks in Python. Compiled from the
official pytorch-v%{version} source tarball (not a PyPI wheel).

2.15 makes the rewritten NCCL backend the default (nccl-legacy,
or TORCH_DIST_USE_NCCL2=0, rolls that back for this release),
adds one-sided distributed transports, and supports torch.compile
on Python 3.15. Official ROCm wheels are 7.14 and 10.0 and drop
gfx906; this package is built against TheRock 10.1 (HIP 7.16)
and still includes gfx906.

GPU:
* ROCm/HIP — AMD (gfx906, gfx908, gfx90a, gfx942, gfx1030,
  gfx1100–1102, gfx1200–1201). This is torch.cuda on Radeon /
  Instinct (ComfyUI, Krita AI).
* Vulkan — in-tree ATen compute backend (USE_VULKAN). The
  desktop torch.device("vulkan") backend is the separate
  python-torchvulkan package.
CUDA is off. Flash-attention/AOTriton is off (it downloads
prebuilt images; ABF has no network). LTO is off (libtorch
link OOMs with full LTO on 64G builders). Distributed is
on (Gloo + RCCL + MPI). Kineto (ROCm profiler) is on.
Bundled CK GEMM/SDPA/MSLK are on (Clang 23 raw_buffer_*
signedness patched). hipFile is on.

%prep
%autosetup -C -n pytorch-v%{version} -p1
# Patch5 covers third_party/composable_kernel. Other vendored CK
# trees (mslk, flash-attn, aiter, fbgemm) get the same rewrite.
python %{SOURCE1} .

%build
# HIP fat binaries × 10 gfx* are RAM-heavy.
# MAX_JOBS is setup.py-era; 2.15's scikit-build-core aliases it
# to CMAKE_BUILD_PARALLEL_LEVEL (setdefault: an explicit value
# wins). Pin both so ninja does not use every core and OOM.
export MAX_JOBS=4
export CMAKE_BUILD_PARALLEL_LEVEL=4
# HIP offload-bundler temps for 10 arches overflow a 32G /tmp tmpfs
# ("No space left on device"). Keep scratch on the build disk.
export TMPDIR=%{_builddir}/.torch-tmp
export TEMP="$TMPDIR"
export TMP="$TMPDIR"
mkdir -p "$TMPDIR"
export CFLAGS='%{torch_cflags}'
export CXXFLAGS='%{torch_cflags}'
# --no-undefined is in distro ldflags. libtorch_python is a Python
# extension: CPython symbols resolve at import time, so LLD must
# allow them. --allow-shlib-undefined is the inverse.
export LDFLAGS="$(printf '%s' '%{?__global_ldflags}' | sed -e 's/-flto=thin//g' -e 's/-flto//g' -e 's/-Wl,--no-undefined//g' -e 's/--no-undefined//g') -Wl,--allow-shlib-undefined"
# OpenMPI wrappers are not on the default PATH.
export PATH=%{_libdir}/openmpi/bin${PATH:+:$PATH}
export MPI_HOME=%{_libdir}/openmpi
export USE_DISTRIBUTED=1
export USE_GLOO=1
export USE_MPI=1
export USE_MKLDNN=1
export USE_NNPACK=0
export USE_QNNPACK=0
export USE_XNNPACK=1
export USE_FBGEMM=0
export USE_KINETO=1
export BUILD_TEST=0
export USE_ITT=0
export USE_OBSERVERS=0
export USE_CUDA=0
export USE_CUDNN=0
# NCCL is the API name; RCCL is the HIP implementation.
# cmake_dependent_option(USE_RCCL) requires USE_NCCL.
# ROCm then forces USE_SYSTEM_NCCL and find_package(rccl).
export USE_NCCL=1
export USE_SYSTEM_NCCL=1
export USE_RCCL=1
export USE_ROCM=1
export USE_VULKAN=1
# Clang 23 signedness of raw_buffer_* is patched (Patch5 + Source1).
export USE_ROCM_CK_GEMM=1
export USE_ROCM_CK_SDPA=1
export USE_MSLK=1
# AOTriton is fetched from GitHub; builders are offline.
export USE_FLASH_ATTENTION=0
export USE_MEM_EFF_ATTENTION=0
# hipfile is packaged (cmake(hipfile)); ROCm >= 7.14 requires it.
export USE_CUFILE=1
export USE_HIPSPARSELT=0
# Distro fmt >= 12 (fmt::fmt-header-only); skip third_party/fmt.
export USE_SYSTEM_FMT=1
# OMV ROCm is FHS, not /opt/rocm. hipcc / clang++ live in /usr/bin.
export ROCM_PATH=%{_prefix}
export HIP_CLANG_PATH=%{_bindir}
export HIP_DEVICE_LIB_PATH=%{_libdir}/amdgcn/bitcode
export PYTORCH_ROCM_ARCH='%{torch_rocm_arch}'
export CMAKE_FRESH=1
# hipcub/rocthrust/rccl *-config.cmake hardcode ${prefix}/lib/cmake
# (Fedora lib) instead of lib64. EnvVarForwarding prepends
# Python sys.prefix (/usr) onto CMAKE_PREFIX_PATH, so the system
# /usr/lib64/cmake/hipcub/config wins and then dies looking for
# /usr/lib/cmake/hipcub/targets. Force find_package onto a shadow
# whose config includes the real lib64 targets file.
_cmpre=%{_builddir}/rocm-prefix
mkdir -p "$_cmpre/include"
# Hipify rewrites nvToolsExt.h to roctracer/roctx.h. ROCTx now lives in
# rocprofiler-sdk-roctx/roctx.h, which already macros the unsuffixed names.
mkdir -p "$_cmpre/include/roctracer"
printf '%s\n' '#include <rocprofiler-sdk-roctx/roctx.h>' > "$_cmpre/include/roctracer/roctx.h"
for pkg in hipcub rocthrust rccl; do
	mkdir -p "$_cmpre/%{_lib}/cmake/${pkg}"
	/bin/cp -f /usr/%{_lib}/cmake/${pkg}/${pkg}-config.cmake \
		/usr/%{_lib}/cmake/${pkg}/${pkg}-config-version.cmake \
		"$_cmpre/%{_lib}/cmake/${pkg}/"
	for f in /usr/%{_lib}/cmake/${pkg}/${pkg}-targets*.cmake; do
		[ -f "$f" ] || continue
		ln -sfn "$f" "$_cmpre/%{_lib}/cmake/${pkg}/"
	done
	sed -i -e "s|\${PACKAGE_PREFIX_DIR}/lib/cmake/${pkg}/|\${CMAKE_CURRENT_LIST_DIR}/|g" \
		"$_cmpre/%{_lib}/cmake/${pkg}/${pkg}-config.cmake"
done
# rccl-targets.cmake sets IMPORTED_LOCATION to ${_IMPORT_PREFIX}/lib/librccl.so.*.
# The shadow makes that prefix rocm-prefix, and the real library is in lib64.
mkdir -p "$_cmpre/lib"
for so in %{_libdir}/librccl.so*; do
	[ -e "$so" ] || continue
	ln -sfn "$so" "$_cmpre/lib/${so##*/}"
done
export hipcub_DIR="$_cmpre/%{_lib}/cmake/hipcub"
export rocthrust_DIR="$_cmpre/%{_lib}/cmake/rocthrust"
export rccl_DIR="$_cmpre/%{_lib}/cmake/rccl"
# scikit-build-core 1.0 prepends /usr via sys.prefix; CMAKE_ARGS
# is the reliable way to pin PackageName_DIR past that.
# LoadHIP caches ROCM_VERSION_HEADER_PATH at hip/hip_version.h
# (HIP_VERSION_*). Kineto reuses that cache and only accepts
# ROCM_VERSION_*, so pin it to the stub below.
export ROCM_VERSION_HEADER_PATH="$_cmpre/include/rocm-core/rocm_version.h"
# /usr/bin/ld is lld. 2.15 uses --symbol-ordering-file on aarch64
# only when CMAKE_LINKER_TYPE is LLD; otherwise it runs ld -verbose
# and expects a GNU linker script.
export CMAKE_ARGS="${CMAKE_ARGS:+$CMAKE_ARGS }-Dhipcub_DIR=$hipcub_DIR -Drocthrust_DIR=$rocthrust_DIR -Drccl_DIR=$rccl_DIR -DROCM_VERSION_HEADER_PATH=$ROCM_VERSION_HEADER_PATH -DCMAKE_LINKER_TYPE=LLD -DCMAKE_CXX_SCAN_FOR_MODULES=OFF"
ln -sfn %{_includedir}/hipcub "$_cmpre/include/hipcub"
ln -sfn %{_includedir}/thrust "$_cmpre/include/thrust"
ln -sfn %{_includedir}/rocprim "$_cmpre/include/rocprim"
# HIP host_defines.h sets `#define __noinline__` (empty) for host C++.
# libstdc++ 16 / libc++ then break: [[__gnu__::__noinline__]] and
# __has_attribute(__noinline__). Copy the hip headers (quoted
# #include "host_defines.h" ignores a shadow) and undo the empty
# macro for host TUs only.
cp -a %{_includedir}/hip "$_cmpre/include/hip"
cat >> "$_cmpre/include/hip/amd_detail/host_defines.h" <<'EOF'

#if !defined(__HIP__)
#ifdef __noinline__
#undef __noinline__
#endif
#endif
EOF
# TheRock 10.1 rocm-core package still has no rocm_version.h.
# TunableOp includes it on Linux. ROCM_VERSION in the C++ sources
# is a HIP-style 7xxxx integer (7.16 -> 71600), not the TheRock
# package number. Reporting 10.1.0 would skip those comparisons.
mkdir -p "$_cmpre/include/rocm-core"
cat > "$_cmpre/include/rocm-core/rocm_version.h" <<'EOF'
/* OMV FHS stub — TheRock 10.1 packaging stream, HIP 7.16 ABI. */
#ifndef _ROCM_VERSION_H_
#define _ROCM_VERSION_H_
#define ROCM_VERSION_MAJOR 7
#define ROCM_VERSION_MINOR 16
#define ROCM_VERSION_PATCH 0
#define ROCM_BUILD_INFO "10.1.0-openmandriva"
#endif
EOF
export CMAKE_PREFIX_PATH="$_cmpre${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
# Release tarball is not a git checkout; without these, setup.py /
# scikit-build-core names the dist 2.15.0a0+gitunknown.
export PYTORCH_BUILD_VERSION=%{version}
export PYTORCH_BUILD_NUMBER=%{release}
if [ -f version.txt ]; then
	echo "%{version}" > version.txt
fi
# Official ROCm step: hipify CUDA → HIP in-place (THC→THH,
# aten/src/ATen/hip/HIPConfig.h.in, c10/hip, …) before cmake.
python tools/amd_build/build_amd.py
test -d aten/src/THH
test -f aten/src/ATen/hip/HIPConfig.h.in

mkdir -p ../RPMBUILD_wheels
CFLAGS='%{torch_cflags}' CXXFLAGS='%{torch_cflags}' \
	pip wheel --wheel-dir ../RPMBUILD_wheels --no-deps --no-build-isolation --verbose .

%install
pip install --root=%{buildroot} --no-deps --verbose --ignore-installed \
	--no-warn-script-location --no-index --no-cache-dir \
	--find-links ../RPMBUILD_wheels ../RPMBUILD_wheels/*.whl
# cmake writes gitignored torch/version.py; the wheel may omit it.
# Without it `import torch` dies (xformers 655854).
python -m tools.generate_torch_version --is-debug=0 \
	--hip-version=7.16 --rocm-version=10.1.0
install -m 644 torch/version.py %{buildroot}%{python_sitearch}/torch/version.py

%files
%license LICENSE
%doc README.md NOTICE
%{_bindir}/torchrun
%{_bindir}/torchfrtrace
# With BUILD_PYTHON=ON the wheel also installs the compat functorch/
# package (earlier HIP builds omitted it; 2.13.0-5 then failed %files).
%{python_sitearch}/functorch
%{python_sitearch}/torch
%{python_sitearch}/torchgen
%{python_sitearch}/torch-%{version}*.dist-info
