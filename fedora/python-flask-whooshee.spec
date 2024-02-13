%global mod_name flask-whooshee

Name:           python-flask-whooshee
Version:        0
Release:        1%{?dist}
Summary:        Whoosh integration

License:        BSD-3-Clause
URL:            https://github.com/fedora-copr/flask-whooshee
Source0:        https://pypi.python.org/packages/source/f/%{mod_name}/%{mod_name}-%{version}.tar.gz
# https://github.com/fedora-copr/flask-whooshee/pull/19
BuildArch:      noarch


%global _description \
Whoosh integration that allows to create and search custom indexes.

%description %{_description}

%package -n python3-%{mod_name}
Summary:        Whoosh integration
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-whoosh
BuildRequires:  python3-flask
BuildRequires:  python3-flask-sqlalchemy
BuildRequires:  python3-flexmock
BuildRequires:  python3-pytest

Requires:       python3-flask-sqlalchemy
Requires:       python3-whoosh
Requires:       python3-flask

%description -n python3-%{mod_name} %{_description}

Python 3 version.

%prep
%autosetup -n %{mod_name}-%{version}

%build
%py3_build

%check
%{__python3} -m pytest -vv test.py


%install
%py3_install


%files -n python3-%{mod_name}
%doc LICENSE README.md
%{python3_sitelib}/__pycache__/*
%{python3_sitelib}/*.egg-info
%{python3_sitelib}/flask_whooshee.py


%changelog
* Wed Apr 05 2023 Pavel Raiskup <praiskup@redhat.com> - 0-1
- no %%changelog for the git main branch
