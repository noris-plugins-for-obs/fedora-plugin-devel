FROM fedora:%dist%

RUN dnf install --setopt=install_weak_deps=False -y obs-studio git createrepo gpg rpm-sign rpm-build gcc && dnf clean all

RUN useradd -u %UID% -s /bin/bash -m user
RUN echo "user ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER user
WORKDIR /home/user
