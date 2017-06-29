FROM kbase/kbase:sdkbase.latest
MAINTAINER KBase Developer
# -----------------------------------------
# In this section, you can install any system dependencies required
# to run your App.  For instance, you could place an apt-get update or
# install line here, a git checkout to download code, or run any other
# installation scripts.

# RUN apt-get update

# Here we install a python coverage tool and an
# https library that is out of date in the base image.

RUN pip install coverage

# update R
RUN CODENAME=`grep CODENAME /etc/lsb-release | cut -c 18-` && \
    echo "deb http://cran.cnr.berkeley.edu/bin/linux/ubuntu $CODENAME/" >> /etc/apt/sources.list && \
    sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys E084DAB9 && \
    sudo apt-get update && \
    yes '' | sudo apt-get -y install r-base && \
    yes '' | sudo apt-get -y install r-base-dev

# -----------------------------------------

# update security libraries in the base image
RUN pip install cffi --upgrade \
    && pip install pyopenssl --upgrade \
    && pip install ndg-httpsclient --upgrade \
    && pip install pyasn1 --upgrade \
    && pip install requests --upgrade \
    && pip install fisher --upgrade \
    && pip install rpy2 --upgrade \
    && pip install 'requests[security]' --upgrade

# -----------------------------------------



COPY ./ /kb/module
RUN mkdir -p /kb/module/work
RUN chmod -R a+rw /kb/module

WORKDIR /kb/module

RUN make all

ENTRYPOINT [ "./scripts/entrypoint.sh" ]

CMD [ ]
