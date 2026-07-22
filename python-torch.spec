%undefine _debugsource_packages

Name:           python-torch
Version:        2.13.0
Release:        3
Summary:        PyTorch machine learning framework (built from source)
License:        BSD-3-Clause
URL:            https://pytorch.org
# Full source bundle published by the PyTorch project (NOT the shallow GitHub
# tag archive — that omits third_party submodules needed to compile).
Source0:        https://github.com/pytorch/pytorch/releases/download/v%{version}/pytorch-v%{version}.tar.gz
# LLD/mold compatibility for aarch64 defaults:
# - USE_PRIORITIZED_TEXT_FOR_LD (symbol-ordering instead of ld -verbose script)
# - skip GNU-ld-only --stub-group-size (LLD rejects it)
Patch0:         pytorch-2.13.0-lld-compat.patch

BuildRequires:  cmake
BuildRequires:  ninja
BuildRequires:  binutils
BuildRequires:  pkgconfig(python3)
BuildRequires:  python%{pyver}dist(setuptools)
BuildRequires:  python%{pyver}dist(wheel)
BuildRequires:  python%{pyver}dist(pip)
BuildRequires:  python%{pyver}dist(numpy)
BuildRequires:  python%{pyver}dist(pyyaml)
BuildRequires:  python%{pyver}dist(typing-extensions)
BuildRequires:  python%{pyver}dist(jinja2)
BuildRequires:  python%{pyver}dist(networkx)
BuildRequires:  python%{pyver}dist(sympy)
BuildRequires:  python%{pyver}dist(fsspec)
BuildRequires:  python%{pyver}dist(filelock)
BuildRequires:  python%{pyver}dist(packaging)

Requires:       python%{pyver}dist(numpy)
Requires:       python%{pyver}dist(typing-extensions)
Requires:       python%{pyver}dist(filelock)
Requires:       python%{pyver}dist(jinja2)
Requires:       python%{pyver}dist(networkx)
Requires:       python%{pyver}dist(fsspec)
Requires:       python%{pyver}dist(sympy)

%description
Tensors and dynamic neural networks in Python with strong GPU acceleration.

%prep
%autosetup -n pytorch-v%{version} -p1

%build
export MAX_JOBS=%{_smp_build_ncpus}
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
export USE_ROCM=0
%if 0%{?with_cuda}
export USE_CUDA=1
export USE_CUDNN=1
%else
export USE_CUDA=0
export USE_CUDNN=0
%endif

# The release tarball is not a git checkout. Without these, setup.py falls back
# to something like "2.13.0a0+gitunknown" for the wheel / dist-info name.
export PYTORCH_BUILD_VERSION=%{version}
export PYTORCH_BUILD_NUMBER=%{release}
# Also keep version.txt in sync if present (some tooling reads it directly).
if [ -f version.txt ]; then
	echo "%{version}" > version.txt
fi

# Build a local wheel from this tree (no PyPI binary torch).
%{__python3} -m pip wheel \
	--wheel-dir %{_builddir}/torch-wheels \
	--no-deps \
	--no-build-isolation \
	--verbose \
	.

%install
%{__python3} -m pip install \
	--no-deps \
	--no-index \
	--find-links %{_builddir}/torch-wheels \
	--root %{buildroot} \
	--prefix %{_prefix} \
	torch

(
	cd %{buildroot}
	find . \( -type f -o -type l \) | sed 's#^\./#/#' | grep -E '/(torch|functorch)(/|-)' || true
) > %{_builddir}/torch-files.list

if [ ! -s %{_builddir}/torch-files.list ]; then
	echo "ERROR: torch install produced no files under buildroot" >&2
	find %{buildroot} | head -80 >&2
	exit 1
fi

%files
%license LICENSE
%doc README.md NOTICE
%{_bindir}/torchrun
%{python_sitearch}/functorch
%{python_sitearch}/torch
%{python_sitearch}/torchgen
%{python_sitearch}/torch-%{version}*.dist-info
