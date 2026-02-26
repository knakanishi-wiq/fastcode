build-local-macos:
    security find-certificate -a -p > /tmp/corp-ca.pem
    docker build \
        --build-arg CERT=1 \
        --secret id=corporate_ca,src=/tmp/corp-ca.pem \
        -t fastcode:test .
