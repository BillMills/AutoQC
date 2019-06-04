FROM ubuntu:16.04

# configure environment for install
RUN apt-get update
RUN apt-get install -y git

# install AutoQC and all deps
RUN git clone -b environment https://github.com/billmills/AutoQC
WORKDIR /AutoQC
RUN sed -i -e 's/sudo //g' install.sh
RUN chmod 777 install.sh
RUN ./install.sh

# add extra datafiles not currently served
COPY data/global_mean_median_quartiles_medcouple_smoothed.nc data/global_mean_median_quartiles_medcouple_smoothed.nc

# set default environment variables
ENV OCEANSDB_DIR /AutoQC/data/
