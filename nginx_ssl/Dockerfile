FROM nginx:alpine
RUN apk add --no-cache bash

ADD conf/nginx.conf /etc/nginx/nginx.conf

ADD script/entrypoint.sh /entrypoint.sh
ADD script/le.sh /le.sh

RUN \
 rm /etc/nginx/conf.d/default.conf && \
 chmod +x /entrypoint.sh && \
 chmod +x /le.sh && \
 apk add --no-cache --update certbot tzdata openssl

CMD ["/entrypoint.sh"]

#ARG USER_ID=1001
#ARG GROUP_ID=1001
#RUN addgroup -g ${GROUP_ID} -S deploy && \
#    adduser -u ${USER_ID} -S -G deploy deploy && \
#    chown -R deploy:deploy /etc/nginx
#
#USER deploy
#ENTRYPOINT ["/entrypoint.sh"]
