FROM almalinux:9 as NITTER_SCRAPER_BUILDER

RUN dnf group install -y 'Development Tools'
RUN bash -c 'curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y'
RUN /root/.cargo/bin/cargo install --git https://github.com/evanc577/nitter-scraper.git


FROM almalinux:9-minimal

WORKDIR /sourcecatcher
RUN microdnf install -y python3 python3-devel python3-pip libdb-devel gcc gcc-c++ redis
COPY requirements.txt /sourcecatcher
RUN pip install -r requirements.txt

COPY systemd/* /etc/systemd/system
RUN systemctl enable redis sourcecatcher

COPY . /sourcecatcher/
COPY --from=NITTER_SCRAPER_BUILDER /root/.cargo/bin/nitter-scraper /usr/local/bin

EXPOSE 80

CMD [ "/sbin/init" ]
