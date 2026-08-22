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
# Skip gfx803 (Polaris): PyTorch 2.13 has no real Polaris kernels;
# ggml / hipBLAS still cover RX 550. hipBLASLt only has navi3x/4x.
%global torch_rocm_arch gfx906;gfx908;gfx90a;gfx942;gfx1030;gfx1100;gfx1101;gfx1102;gfx1200;gfx1201

Name:		python-torch
Version:	2.13.0
Release:	5
Summary:	PyTorch machine learning framework
License:	BSD-3-Clause
Group:		Development/Python
URL:		https://pytorch.org
# Full source bundle from the PyTorch project. The GitHub tag archive
# omits third_party submodules needed to compile.
Source0:	https://github.com/pytorch/pytorch/releases/download/v%{version}/pytorch-v%{version}.tar.gz
# LLD/mold: skip GNU-ld-only --stub-group-size; prioritized-text
# uses --symbol-ordering-file instead of a BFD -T script.
Patch0:		pytorch-2.13.0-lld-compat.patch
# TheRock 7.14 has no roctracer libroctx64. ROCTx markers are optional.
Patch1:		pytorch-2.13.0-optional-roctx.patch
# Clang 23: amdgcn buffer load/store builtins return/take unsigned
# vector types; CK headers still use signed int32xN_t.
Patch2:		pytorch-2.13.0-ck-clang23-buffer-builtins.patch
# cmake_dependent_option ignores USE_FLASH_ATTENTION=0 from the env
# and git-clones aotriton_runtime (no network on ABF).
Patch3:		pytorch-2.13.0-no-aotriton-fetch.patch

BuildRequires:	python
# find_package(Python COMPONENTS Development.Module) — without
# this cmake silently sets BUILD_PYTHON=OFF and the wheel has no
# torch/_C*.so (xformers 656372: Failed to load PyTorch C extensions).
BuildRequires:	pkgconfig(python)
BuildRequires:	cmake
BuildRequires:	ninja
BuildRequires:	binutils
BuildRequires:	python%{pyver}dist(setuptools)
BuildRequires:	python%{pyver}dist(wheel)
BuildRequires:	python%{pyver}dist(pip)
BuildRequires:	python%{pyver}dist(numpy)
BuildRequires:	python%{pyver}dist(pyyaml)
BuildRequires:	python%{pyver}dist(typing-extensions)
BuildRequires:	python%{pyver}dist(jinja2)
BuildRequires:	python%{pyver}dist(networkx)
BuildRequires:	python%{pyver}dist(sympy)
BuildRequires:	python%{pyver}dist(fsspec)
BuildRequires:	python%{pyver}dist(filelock)
BuildRequires:	python%{pyver}dist(packaging)

# ROCm 7.14 (FHS /usr, not /opt/rocm)
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
BuildRequires:	cmake(hiprtc)
BuildRequires:	cmake(hipcub)
BuildRequires:	cmake(rocprim)
BuildRequires:	cmake(rocthrust)
BuildRequires:	cmake(rocrand)
BuildRequires:	rocm-runtime-devel
BuildRequires:	cmake(rocm_smi)
# rocm_smi-config.cmake does pkg_check_modules(libdrm REQUIRED).
BuildRequires:	pkgconfig(libdrm)
# c10d/symm_mem/intra_node_comm.cpp includes <amd_smi/amdsmi.h>
BuildRequires:	cmake(amd_smi)
# ATen Vulkan (desktop): system loader + glslc for shader codegen.
BuildRequires:	pkgconfig(vulkan)
BuildRequires:	glslc

Requires:	python%{pyver}dist(numpy)
Requires:	python%{pyver}dist(typing-extensions)
Requires:	python%{pyver}dist(filelock)
Requires:	python%{pyver}dist(jinja2)
Requires:	python%{pyver}dist(networkx)
Requires:	python%{pyver}dist(fsspec)
Requires:	python%{pyver}dist(sympy)
# HIP/Vulkan .so deps come from the ELF generator. Recommend the
# pieces that are useful at runtime but not always DT_NEEDED.
Recommends:	miopen%{?_isa}
Recommends:	hipblaslt%{?_isa}

%description
Tensors and dynamic neural networks in Python. Compiled from the
official pytorch-v%{version} source tarball (not a PyPI wheel).

GPU:
* ROCm/HIP — AMD (gfx906, gfx908, gfx90a, gfx942, gfx1030,
  gfx1100–1102, gfx1200–1201). This is torch.cuda on Radeon /
  Instinct (ComfyUI, Krita AI).
* Vulkan — ATen compute backend (Intel / AMD / wherever a
  Vulkan 1.x driver exists). Not the Intel XPU/SYCL stack.
CUDA is off. Flash-attention/AOTriton is off (it downloads
prebuilt images; ABF has no network). LTO is off (libtorch
link OOMs with full LTO on 64G builders). Bundled CK GEMM/
SDPA/MSLK are off until Composable Kernel is fixed for
Clang 23 vector builtin types.

%prep
%autosetup -C -n pytorch-v%{version} -p1

%build
# HIP fat binaries × 10 gfx* are RAM-heavy.
export MAX_JOBS=4
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
export USE_DISTRIBUTED=0
export USE_MKLDNN=1
export USE_NNPACK=0
export USE_QNNPACK=0
export USE_XNNPACK=1
export USE_FBGEMM=0
export USE_KINETO=0
export BUILD_TEST=0
export USE_ITT=0
export USE_OBSERVERS=0
export USE_CUDA=0
export USE_CUDNN=0
export USE_NCCL=0
export USE_RCCL=0
export USE_ROCM=1
export USE_VULKAN=1
# Bundled Composable Kernel headers break on Clang 23 signedness of
# amdgcn vector builtins (int32xN vs unsigned). hipBLAS/MIOpen still
# cover GEMM/conv; CK GEMM/SDPA/MSLK can return once CK is fixed.
export USE_ROCM_CK_GEMM=0
export USE_ROCM_CK_SDPA=0
export USE_MSLK=0
# AOTriton is fetched from GitHub; builders are offline.
export USE_FLASH_ATTENTION=0
export USE_MEM_EFF_ATTENTION=0
# OMV ROCm is FHS, not /opt/rocm. hipcc / clang++ live in /usr/bin.
export ROCM_PATH=%{_prefix}
export HIP_CLANG_PATH=%{_bindir}
export HIP_DEVICE_LIB_PATH=%{_libdir}/amdgcn/bitcode
export PYTORCH_ROCM_ARCH='%{torch_rocm_arch}'
export CMAKE_FRESH=1
# hipcub/rocthrust *-config.cmake hardcode ${prefix}/lib/cmake
# (Fedora lib) instead of lib64. Shadow them with a tiny prefix
# so PACKAGE_PREFIX_DIR/lib/cmake/... resolves.
_cmpre=%{_builddir}/rocm-prefix
mkdir -p "$_cmpre/include"
for pkg in hipcub rocthrust; do
	mkdir -p "$_cmpre/lib/cmake/${pkg}" "$_cmpre/%{_lib}/cmake/${pkg}"
	/bin/cp -f /usr/%{_lib}/cmake/${pkg}/${pkg}-config.cmake \
		/usr/%{_lib}/cmake/${pkg}/${pkg}-config-version.cmake \
		"$_cmpre/%{_lib}/cmake/${pkg}/"
	for f in /usr/%{_lib}/cmake/${pkg}/${pkg}-targets*.cmake; do
		[ -f "$f" ] || continue
		ln -sfn "$f" "$_cmpre/lib/cmake/${pkg}/"
	done
done
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
# TheRock 7.14 OMV packages do not ship rocm-core/rocm_version.h
# (only a leftover /opt/rocm-*). TunableOp includes it on Linux.
mkdir -p "$_cmpre/include/rocm-core"
cat > "$_cmpre/include/rocm-core/rocm_version.h" <<'EOF'
/* OMV FHS stub — matches TheRock 7.14 packaging stream. */
#ifndef _ROCM_VERSION_H_
#define _ROCM_VERSION_H_
#define ROCM_VERSION_MAJOR 7
#define ROCM_VERSION_MINOR 14
#define ROCM_VERSION_PATCH 0
#define ROCM_BUILD_INFO "7.14.0-openmandriva"
#endif
EOF
export CMAKE_PREFIX_PATH="$_cmpre${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
# Release tarball is not a git checkout; without these, setup.py
# names the dist 2.13.0a0+gitunknown.
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
# cmake writes gitignored torch/version.py; setuptools/pip wheel
# does not ship it. Without it `import torch` dies (xformers 655854).
python -m tools.generate_torch_version --is-debug=0 \
	--hip-version=7.14 --rocm-version=7.14.0
install -m 644 torch/version.py %{buildroot}%{python_sitearch}/torch/version.py

%files
%license LICENSE
%doc README.md NOTICE
%{_bindir}/torchrun
# 2.13 ships functorch as torch/_functorch, not a top-level package
%{python_sitearch}/torch
%{python_sitearch}/torchgen
%{python_sitearch}/torch-%{version}*.dist-info
