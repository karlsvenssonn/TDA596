for i in `seq 1 6`; do
curl -d 'entry=t'${1} -X 'POST' 'http://10.1.0.'${1}'/board' &
done
