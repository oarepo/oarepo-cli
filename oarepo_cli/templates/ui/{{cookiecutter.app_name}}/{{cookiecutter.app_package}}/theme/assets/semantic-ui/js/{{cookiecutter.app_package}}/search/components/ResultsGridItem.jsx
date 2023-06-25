import PropTypes from "prop-types";
import { withState } from "react-searchkit";

// TODO: Update this according to the full List item template?
export const ResultsGridItem = ({ result }) => {
  return (
    <Card fluid href={`/docs/${result.links.self}`}>
      <Card.Content>
        <Card.Header>{result.metadata.record.title}</Card.Header>
        <Card.Description>
        </Card.Description>
      </Card.Content>
    </Card>
  );
};

ResultsGridItem.propTypes = {
  result: PropTypes.object.isRequired,
};

export const ResultsGridItemWithState = withState(
  ({ currentQueryState, result, appName }) => (
    <ResultsGridItem
      currentQueryState={currentQueryState}
      result={result}
      appName={appName}
    />
  )
);

ResultsGridItemWithState.propTypes = {
  currentQueryState: PropTypes.object,
  result: PropTypes.object.isRequired,
};

ResultsGridItemWithState.defaultProps = {
  currentQueryState: null,
};
