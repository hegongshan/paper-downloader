### Academic Paper Bulk Downloader for Open Access Venues (APBDOAV)

#### Install dependencies

```shell
$ pip3 install -r requirements.txt
```

#### Usage

```shell
$ python3 cli.py --help
usage: cli.py [-h] --venue VENUE [--save-dir SAVE_DIR] [--log-file LOG_FILE]
              [--sleep-time-per-paper SLEEP_TIME_PER_PAPER] [--keyword KEYWORD] [--year YEAR]
              [--volume VOLUME] [--http-proxy HTTP_PROXY] [--https-proxy HTTPS_PROXY] [--parallel]

Run PDL.

options:
  -h, --help            show this help message and exit
  --venue VENUE         Available value = fast,osdi,atc,nsdi,uss,ndss,aaai,ijcai,cvpr,iccv,eccv,iclr,icml,neu
                        rips,nips,acl,emnlp,naacl,rss,pvldb,jmlr.
  --save-dir SAVE_DIR   Set a directory to store these papers. (default value: "./paper")
  --log-file LOG_FILE   The filename of the log. (default value: "paper-downloader.log")
  --sleep-time-per-paper SLEEP_TIME_PER_PAPER
                        The time interval between downloads, measured in seconds. (default value: 2)
  --keyword KEYWORD     The keywords or regex patterns that must be present or matched in the title of the
                        paper.
  --year YEAR           The year of the conference.
  --volume VOLUME       The volume number of the journal.
  --http-proxy HTTP_PROXY
                        HTTP Proxy server.
  --https-proxy HTTPS_PROXY
                        HTTPS Proxy server.
  --parallel            Use parallel downloads.
```

* Example

```shell
$ python3 cli.py --venue fast --year 2023
```

* Supported Venue

<table>
    <tr>
        <th>Areas</th>
        <th>Sub Areas</th>
        <th>Conf/Journal</th>
        <th>URL</th>
    </tr>
	<tr>
        <td rowspan="12">AI</td>
        <td rowspan="2">Artificial intelligents</td>
        <td>AAAI</td>
        <td>
            <a href="https://aaai.org/aaai-publications/aaai-conference-proceedings/">
            	https://aaai.org/aaai-publications/aaai-conference-proceedings/
            </a>
        </td>
	</tr>
	<tr>
        <td>IJCAI</td>
        <td>
            <a href="https://www.ijcai.org/all_proceedings">https://www.ijcai.org/all_proceedings</a>
        </td>
	</tr>
	<tr>
        <td rowspan="3">Computer vision</td>
        <td>CVPR</td>
        <td>
			<a href="https://openaccess.thecvf.com/menu">https://openaccess.thecvf.com/menu</a>
        </td>
    </tr>
    <tr>
        <td>ICCV</td>
        <td>
            <a href="https://openaccess.thecvf.com/menu">https://openaccess.thecvf.com/menu</a>
        </td>
    </tr>
    <tr>
        <td>ECCV</td>
        <td>
            <a href="https://www.ecva.net/papers.php">https://www.ecva.net/papers.php</a>
        </td>
    </tr>
    <tr>
        <td rowspan="4">Machine Learning</td>
        <td>ICLR</td>
        <td><a href="https://dblp.uni-trier.de/db/conf/iclr/index.html">https://dblp.uni-trier.de/db/conf/iclr/index.html</a></td>
    </tr>
    <tr>
        <td>ICML</td>
        <td>
            <a href="https://dblp.uni-trier.de/db/conf/icml/index.html">https://dblp.uni-trier.de/db/conf/icml/index.html</a>
        </td>
    </tr>
    <tr>
        <td>NeurIPS</td>
        <td>
            <a href="https://papers.nips.cc/">https://papers.nips.cc/</a>
        </td>
    </tr>
    <tr>
        <td>JMLR</td>
        <td>
            <a href="https://jmlr.org/papers/">https://jmlr.org/papers/</a>
        </td>
    </tr>
	<tr>
        <td rowspan="3">Natural language processing</td>
        <td>ACL</td>
        <td>
            <a href="https://aclanthology.org/">https://aclanthology.org/</a>
        </td>
	</tr>
	<tr>
        <td>
            EMNLP
        </td>
        <td>
            <a href="https://aclanthology.org/">https://aclanthology.org/</a>
        </td>
	</tr>
	<tr>
        <td>
            NAACL
        </td>
        <td>
            <a href="https://aclanthology.org/">https://aclanthology.org/</a>
        </td>
	</tr>
	<tr>
        <td rowspan="7">System</td>
        <td>Computer networks</td>
        <td>NSDI</td>
        <td>
            <a href="https://www.usenix.org/conference/">https://www.usenix.org/conference/</a>
        </td>
	</tr>
	<tr>
        <td rowspan="1">Databases</td>
        <td>VLDB</td>
        <td><a href="https://vldb.org/pvldb">https://vldb.org/pvldb</a></td>
	</tr>
	<tr>
        <td rowspan="2">Computer security</td>
        <td>USENIX Security</td>
        <td>
            <a href="https://www.usenix.org/conference/">https://www.usenix.org/conference/</a>
        </td>
	</tr>
	<tr>
        <td>NDSS</td>
        <td>
            <a href="https://www.ndss-symposium.org/">https://www.ndss-symposium.org/</a>
        </td>
	</tr>
	<tr>
		<td rowspan="3">Operating systems</td>
		<td>OSDI</td>
		<td>
			<a  href="https://www.usenix.org/conferences/past">https://www.usenix.org/conferences/past</a>
		</td>
	</tr>
	<tr>
		<td>FAST</td>
		<td>
		<a  href="https://www.usenix.org/conferences/past">https://www.usenix.org/conferences/past</a>
		</td>
	</tr>
	<tr>
		<td>USENIX ATC</td>
		<td>
		<a  href="https://www.usenix.org/conferences/past">https://www.usenix.org/conferences/past</a>
		</td>
	</tr>
	<tr>
        <td>Interdisciplinary Areas</td>
        <td>Robotics</td>
        <td>RSS</td>
        <td>
            <a href="https://www.roboticsproceedings.org/">https://www.roboticsproceedings.org/</a>
        </td>
	</tr>
</table>

