FROM almalinux:9 as builder
RUN dnf group install -y 'Development Tools'
RUN bash -c 'curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y'
ENV PATH=/root/.cargo/bin:$PATH
RUN bash -c 'curl https://nim-lang.org/choosenim/init.sh -sSf | sh -s -- -y'
ENV PATH=/root/.nimble/bin:$PATH


FROM builder as nitter-scraper-builder
RUN cargo install --git https://github.com/evanc577/nitter-scraper.git


FROM builder as discord-scraper-builder
RUN dnf install -y openssl-devel
RUN cargo install --git https://github.com/evanc577/sourcecatcher-discord-scraper.git


FROM builder as nitter-builder
RUN dnf install -y epel-release
RUN dnf install -y libsass-devel
WORKDIR /src
RUN git clone https://github.com/zedeus/nitter
WORKDIR /src/nitter
RUN nimble build -d:danger -d:lto -d:strip --mm:refc && nimble scss && nimble md


FROM almalinux:9-minimal

WORKDIR /sourcecatcher
RUN microdnf install -y python3 python3-devel python3-pip libdb-devel gcc gcc-c++ redis
COPY requirements.txt /sourcecatcher
RUN pip install -r requirements.txt

RUN useradd -c "Nitter user" -d /nitter -s /bin/sh nitter

COPY systemd/* /etc/systemd/system
RUN systemctl enable redis nitter sourcecatcher

COPY src/ /sourcecatcher/src/
COPY scripts/ /sourcecatcher/scripts/
COPY --from=nitter-scraper-builder /root/.cargo/bin/nitter-scraper /usr/local/bin
COPY --from=discord-scraper-builder /root/.cargo/bin/sourcecatcher-discord-scraper /usr/local/bin

COPY nitter/nitter.conf /nitter
COPY --from=nitter-builder /src/nitter/nitter /usr/local/bin
COPY --from=nitter-builder /src/nitter/public /nitter/public
RUN chown -R nitter:nitter /nitter

EXPOSE 80

CMD ["/sbin/init"]
