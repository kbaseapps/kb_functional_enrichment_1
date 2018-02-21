
package us.kbase.kbfunctionalenrichment1;

import java.util.HashMap;
import java.util.Map;
import javax.annotation.Generated;
import com.fasterxml.jackson.annotation.JsonAnyGetter;
import com.fasterxml.jackson.annotation.JsonAnySetter;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyOrder;


/**
 * <p>Original spec-file type: FEOneInput</p>
 * <pre>
 * required params:
 * feature_set_ref: FeatureSet object reference
 * workspace_name: the name of the workspace it gets saved to
 * optional params:
 * propagation: includes is_a relationship to all go terms (default is 1)
 * filter_ref_features: filter reference genome features with no go terms (default is 0)
 * statistical_significance: parameter for statistical significance. Select one from left_tailed, right_tailed or two_tailed (default is left_tailed)
 * ignore_go_term_not_in_feature_set: ignore Go term analysis if term is not associated with FeatureSet (default is 1)
 * </pre>
 * 
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
@Generated("com.googlecode.jsonschema2pojo")
@JsonPropertyOrder({
    "feature_set_ref",
    "workspace_name",
    "propagation",
    "filter_ref_features",
    "statistical_significance",
    "ignore_go_term_not_in_feature_set"
})
public class FEOneInput {

    @JsonProperty("feature_set_ref")
    private String featureSetRef;
    @JsonProperty("workspace_name")
    private String workspaceName;
    @JsonProperty("propagation")
    private Long propagation;
    @JsonProperty("filter_ref_features")
    private Long filterRefFeatures;
    @JsonProperty("statistical_significance")
    private String statisticalSignificance;
    @JsonProperty("ignore_go_term_not_in_feature_set")
    private Long ignoreGoTermNotInFeatureSet;
    private Map<String, Object> additionalProperties = new HashMap<String, Object>();

    @JsonProperty("feature_set_ref")
    public String getFeatureSetRef() {
        return featureSetRef;
    }

    @JsonProperty("feature_set_ref")
    public void setFeatureSetRef(String featureSetRef) {
        this.featureSetRef = featureSetRef;
    }

    public FEOneInput withFeatureSetRef(String featureSetRef) {
        this.featureSetRef = featureSetRef;
        return this;
    }

    @JsonProperty("workspace_name")
    public String getWorkspaceName() {
        return workspaceName;
    }

    @JsonProperty("workspace_name")
    public void setWorkspaceName(String workspaceName) {
        this.workspaceName = workspaceName;
    }

    public FEOneInput withWorkspaceName(String workspaceName) {
        this.workspaceName = workspaceName;
        return this;
    }

    @JsonProperty("propagation")
    public Long getPropagation() {
        return propagation;
    }

    @JsonProperty("propagation")
    public void setPropagation(Long propagation) {
        this.propagation = propagation;
    }

    public FEOneInput withPropagation(Long propagation) {
        this.propagation = propagation;
        return this;
    }

    @JsonProperty("filter_ref_features")
    public Long getFilterRefFeatures() {
        return filterRefFeatures;
    }

    @JsonProperty("filter_ref_features")
    public void setFilterRefFeatures(Long filterRefFeatures) {
        this.filterRefFeatures = filterRefFeatures;
    }

    public FEOneInput withFilterRefFeatures(Long filterRefFeatures) {
        this.filterRefFeatures = filterRefFeatures;
        return this;
    }

    @JsonProperty("statistical_significance")
    public String getStatisticalSignificance() {
        return statisticalSignificance;
    }

    @JsonProperty("statistical_significance")
    public void setStatisticalSignificance(String statisticalSignificance) {
        this.statisticalSignificance = statisticalSignificance;
    }

    public FEOneInput withStatisticalSignificance(String statisticalSignificance) {
        this.statisticalSignificance = statisticalSignificance;
        return this;
    }

    @JsonProperty("ignore_go_term_not_in_feature_set")
    public Long getIgnoreGoTermNotInFeatureSet() {
        return ignoreGoTermNotInFeatureSet;
    }

    @JsonProperty("ignore_go_term_not_in_feature_set")
    public void setIgnoreGoTermNotInFeatureSet(Long ignoreGoTermNotInFeatureSet) {
        this.ignoreGoTermNotInFeatureSet = ignoreGoTermNotInFeatureSet;
    }

    public FEOneInput withIgnoreGoTermNotInFeatureSet(Long ignoreGoTermNotInFeatureSet) {
        this.ignoreGoTermNotInFeatureSet = ignoreGoTermNotInFeatureSet;
        return this;
    }

    @JsonAnyGetter
    public Map<String, Object> getAdditionalProperties() {
        return this.additionalProperties;
    }

    @JsonAnySetter
    public void setAdditionalProperties(String name, Object value) {
        this.additionalProperties.put(name, value);
    }

    @Override
    public String toString() {
        return ((((((((((((((("FEOneInput"+" [featureSetRef=")+ featureSetRef)+", workspaceName=")+ workspaceName)+", propagation=")+ propagation)+", filterRefFeatures=")+ filterRefFeatures)+", statisticalSignificance=")+ statisticalSignificance)+", ignoreGoTermNotInFeatureSet=")+ ignoreGoTermNotInFeatureSet)+", additionalProperties=")+ additionalProperties)+"]");
    }

}
